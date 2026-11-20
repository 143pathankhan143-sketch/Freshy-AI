import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ai.conversation_store import ConversationStore
from memory.schemas import MemoryCandidate, MemorySettings
from memory.store import MemoryStore


class MemoryStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.temp.name, "memory.db")
        self.store = MemoryStore(
            self.path,
            MemorySettings(max_items=10, persist_conversations=True),
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_memory_survives_store_restart_and_duplicate_is_reused(self):
        candidate = MemoryCandidate(
            category="profile", key="name", value="Pathan", importance=5
        )
        first, created = self.store.add_memory(candidate, session_id="one")
        self.assertTrue(created)
        duplicate, created_again = self.store.add_memory(candidate, session_id="two")
        self.assertFalse(created_again)
        self.assertEqual(first.id, duplicate.id)

        reopened = MemoryStore(self.path, MemorySettings())
        items, total = reopened.list_memories()
        self.assertEqual(total, 1)
        self.assertEqual(items[0].value, "Pathan")

    def test_persistent_conversation_history_loads_after_restart(self):
        conversation = ConversationStore(
            max_messages=8,
            max_characters=2000,
            persistence=self.store,
        )
        conversation.add_message("session-a", "user", "Mera naam Pathan hai")
        conversation.add_message("session-a", "assistant", "Theek hai")

        reopened = MemoryStore(self.path, MemorySettings())
        conversation_after_restart = ConversationStore(
            max_messages=8,
            max_characters=2000,
            persistence=reopened,
        )
        history = conversation_after_restart.get_history("session-a")
        self.assertEqual([item.role for item in history], ["user", "assistant"])
        self.assertIn("Pathan", history[0].content)
        self.assertTrue(conversation_after_restart.clear_session("session-a"))
        self.assertEqual(conversation_after_restart.get_history("session-a"), [])

    def test_memory_limit_prunes_unpinned_low_priority_items(self):
        self.store.update_settings({"max_items": 10})
        for index in range(12):
            self.store.add_memory(
                MemoryCandidate(
                    category="note",
                    key=f"note-{index}",
                    value=f"value-{index}",
                    importance=1,
                ),
                pinned=index == 0,
            )
        items, total = self.store.list_memories(limit=20)
        self.assertEqual(total, 10)
        self.assertTrue(any(item.key == "note-0" and item.pinned for item in items))

    def test_persistent_history_omits_secrets_and_stays_bounded(self):
        conversation = ConversationStore(
            max_messages=4,
            max_characters=2000,
            persistence=self.store,
        )
        for index in range(6):
            conversation.add_message("secure", "user", f"normal message {index}")
        conversation.add_message(
            "secure", "user", "My API key is sk-abcdefghijklmnop"
        )
        reopened = MemoryStore(self.path, MemorySettings())
        rows = reopened.load_conversation_messages("secure", 20, 10000)
        self.assertEqual(len(rows), 4)
        rendered = " ".join(str(row["content"]) for row in rows)
        self.assertNotIn("sk-abcdefghijklmnop", rendered)

    def test_export_is_duplicate_safe_and_clear_conversations_keeps_memories(self):
        self.store.add_memory(
            MemoryCandidate(category="profile", key="name", value="Pathan")
        )
        self.store.add_conversation_message("s", "user", "hello")
        backup = self.store.export_memories()
        self.assertEqual(backup["format"], "freshy-memory-export-v1")
        self.assertEqual(len(backup["items"]), 1)
        sessions, messages = self.store.clear_all_conversations()
        self.assertEqual((sessions, messages), (1, 1))
        self.assertEqual(self.store.count_memories()[0], 1)


if __name__ == "__main__":
    unittest.main()
