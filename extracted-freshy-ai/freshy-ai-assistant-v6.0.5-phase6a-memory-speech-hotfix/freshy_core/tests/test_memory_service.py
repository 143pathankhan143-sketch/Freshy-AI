import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from memory.schemas import MemorySettings
from memory.service import MemoryService
from memory.store import MemoryStore


class MemoryServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = MemoryStore(
            os.path.join(self.temp.name, "memory.db"),
            MemorySettings(
                mode="ask_before_saving",
                auto_profile_detection=True,
                persist_conversations=True,
            ),
        )
        self.service = MemoryService(store=self.store)

    def tearDown(self):
        self.temp.cleanup()

    def test_implicit_profile_fact_asks_then_saves_after_yes(self):
        pending = self.service.process_control_message("s", "Mera naam Pathan hai")
        self.assertIsNotNone(pending)
        self.assertTrue(pending.pending_confirmation)
        self.assertEqual(self.store.count_memories()[0], 0)

        saved = self.service.process_control_message("s", "haan")
        self.assertTrue(saved.success)
        self.assertEqual(self.store.count_memories()[0], 1)

        answer = self.service.process_control_message("s", "Mera naam kya hai?")
        self.assertIsNotNone(answer)
        self.assertIn("Pathan", answer.reply)
        self.assertEqual(answer.speech_text, "Aapka naam Pathan hai.")
        self.assertNotIn("1.", answer.speech_text)
        self.assertNotIn("Name:", answer.speech_text)

    def test_memory_list_keeps_formatted_chat_but_uses_short_natural_speech(self):
        self.service.process_control_message(
            "s", "remember that my active project is Freshy AI Assistant"
        )
        self.service.process_control_message(
            "s", "remember that I prefer Hindi for explanations"
        )
        result = self.service.process_control_message("s", "show my memories")
        self.assertIsNotNone(result)
        self.assertIn("1.", result.reply)
        self.assertIn("2.", result.reply)
        self.assertEqual(
            result.speech_text,
            "Mujhe aapke baare mein 2 baatein yaad hain. Details chat mein dikh rahi hain.",
        )
        self.assertNotIn("1.", result.speech_text)
        self.assertNotIn("2.", result.speech_text)

    def test_explicit_remember_command_saves_without_extra_confirmation(self):
        result = self.service.process_control_message(
            "s", "Freshy, yaad rakho ki mera project Freshy AI hai"
        )
        self.assertTrue(result.success)
        self.assertFalse(result.pending_confirmation)
        items, total = self.store.list_memories()
        self.assertEqual(total, 1)
        self.assertIn("Freshy AI", items[0].value)

    def test_secret_is_rejected(self):
        result = self.service.process_control_message(
            "s", "remember that my API key is sk-abcdefghijklmnop"
        )
        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "unsafe_memory")
        self.assertEqual(self.store.count_memories()[0], 0)

    def test_recall_selects_relevant_memory_not_everything(self):
        self.service.process_control_message(
            "s", "remember that my active project is Freshy AI Assistant"
        )
        self.service.process_control_message(
            "s", "remember that I prefer Hindi for explanations"
        )
        recall = self.service.recall("Explain my Freshy project architecture")
        self.assertTrue(recall.records)
        self.assertIn("Freshy", recall.context)
        self.assertLessEqual(len(recall.records), self.service.settings.recall_limit)

    def test_forget_command_deletes_matching_memory(self):
        self.service.process_control_message(
            "s", "remember that my project is Freshy AI"
        )
        result = self.service.process_control_message("s", "forget Freshy AI")
        self.assertTrue(result.success)
        self.assertEqual(self.store.count_memories()[0], 0)


if __name__ == "__main__":
    unittest.main()
