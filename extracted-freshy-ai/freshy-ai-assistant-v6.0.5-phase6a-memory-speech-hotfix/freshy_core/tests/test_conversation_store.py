import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ai.conversation_store import ConversationStore


class ConversationStoreTests(unittest.TestCase):
    def test_history_is_bounded_by_count(self):
        store = ConversationStore(max_messages=3, max_characters=1000)
        for index in range(5):
            store.add_message("s", "user", f"message-{index}")
        history = store.get_history("s")
        self.assertEqual(len(history), 3)
        self.assertEqual(history[0].content, "message-2")

    def test_history_is_bounded_by_characters_even_for_one_large_message(self):
        store = ConversationStore(max_messages=10, max_characters=20)
        store.add_message("s", "user", "x" * 100)
        history = store.get_history("s")
        self.assertLessEqual(sum(len(item.content) for item in history), 20)

    def test_session_isolation_and_clear(self):
        store = ConversationStore(max_messages=10, max_characters=1000)
        store.add_message("a", "user", "alpha")
        store.add_message("b", "user", "beta")
        self.assertEqual(store.get_history("a")[0].content, "alpha")
        self.assertTrue(store.clear_session("a"))
        self.assertEqual(store.get_history("a"), [])
        self.assertEqual(store.get_history("b")[0].content, "beta")


if __name__ == "__main__":
    unittest.main()
