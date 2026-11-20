import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
import main
from ai.conversation_store import ConversationStore
from memory.schemas import MemorySettings
from memory.service import MemoryService
from memory.store import MemoryStore


class NullTTS:
    class Settings:
        enabled = False
        startup_greeting = False

        def model_dump(self):
            return {"enabled": False, "startup_greeting": False}

    settings = Settings()

    def speak(self, text, prepared_audio_token=None):
        return {"accepted": False, "reason": "disabled"}

    def get_status(self):
        return {"is_speaking": False, "queue_size": 0, "enabled": False}

    def shutdown(self):
        return {"accepted": True}


class Phase5ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        store = MemoryStore(
            os.path.join(cls.temp.name, "memory.db"),
            MemorySettings(mode="ask_before_saving"),
        )
        main.orchestrator.memory_service = MemoryService(store=store)
        main.orchestrator.conversation_store = ConversationStore(
            max_messages=16,
            max_characters=24000,
            persistence=store,
        )
        main.set_tts_service(NullTTS())
        cls.client = TestClient(main.app)

    @classmethod
    def tearDownClass(cls):
        main.set_tts_service(None)
        cls.temp.cleanup()

    def setUp(self):
        main.orchestrator.memory_service.store.clear_memories()
        main.orchestrator.memory_service.store.clear_all_conversations()
        main.orchestrator.conversation_store.clear_all()

    def test_memory_crud_and_status_are_credential_free(self):
        created = self.client.post(
            "/api/memory",
            json={
                "category": "project",
                "key": "active_project",
                "value": "Freshy AI Assistant",
                "tags": ["freshy"],
                "importance": 5,
                "pinned": True,
            },
        )
        self.assertEqual(created.status_code, 200)
        memory_id = created.json()["item"]["id"]

        listed = self.client.get("/api/memory?category=project")
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.json()["total"], 1)

        status = self.client.get("/api/memory/status")
        self.assertEqual(status.status_code, 200)
        rendered = str(status.json()).lower()
        self.assertNotIn("api_key", rendered)
        self.assertEqual(status.json()["memory_count"], 1)

        deleted = self.client.delete(f"/api/memory/{memory_id}")
        self.assertEqual(deleted.status_code, 200)

    def test_secret_memory_is_rejected_and_clear_requires_confirmation(self):
        rejected = self.client.post(
            "/api/memory",
            json={
                "category": "note",
                "key": "api_key",
                "value": "sk-abcdefghijklmnop",
            },
        )
        self.assertEqual(rejected.status_code, 400)

        no_confirm = self.client.post("/api/memory/clear", json={"confirm": False})
        self.assertEqual(no_confirm.status_code, 400)

    def test_chat_contract_includes_optional_memory_metadata(self):
        response = self.client.post(
            "/api/chat",
            json={"message": "Mera naam Pathan hai", "session_id": "phase5"},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["provider"], "memory")
        self.assertTrue(data["memory_pending"])
        self.assertIn("memory_used", data)
        self.assertIn("memory_count", data)


    def test_export_import_and_conversation_clear(self):
        created = self.client.post(
            "/api/memory",
            json={"category": "profile", "key": "name", "value": "Pathan"},
        )
        self.assertEqual(created.status_code, 200)
        backup = self.client.get("/api/memory/export")
        self.assertEqual(backup.status_code, 200)
        self.assertEqual(backup.json()["format"], "freshy-memory-export-v1")

        imported = self.client.post(
            "/api/memory/import",
            json={"items": backup.json()["items"], "replace_existing": False},
        )
        self.assertEqual(imported.status_code, 200)
        self.assertGreaterEqual(imported.json()["skipped"], 1)

        main.orchestrator.conversation_store.add_message("saved", "user", "hello")
        cleared = self.client.post(
            "/api/memory/conversations/clear", json={"confirm": True}
        )
        self.assertEqual(cleared.status_code, 200)
        self.assertGreaterEqual(cleared.json()["deleted_messages"], 1)


if __name__ == "__main__":
    unittest.main()
