import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from intents import RuleBasedIntentParser

class TestRuleBasedIntentParser(unittest.TestCase):

    def test_greeting_detection(self):
        intent = RuleBasedIntentParser.parse("Hello Freshy, how are you?")
        self.assertEqual(intent.name, "GREETING")
        self.assertGreaterEqual(intent.confidence, 0.9)

    def test_short_chat_greeting_variants_are_local(self):
        for message in ("hy", "hii", "heyy", "heuy"):
            with self.subTest(message=message):
                intent = RuleBasedIntentParser.parse(message)
                self.assertEqual(intent.name, "GREETING")

    def test_time_query_detection(self):
        intent = RuleBasedIntentParser.parse("What time is it right now?")
        self.assertEqual(intent.name, "TIME_DATE")

    def test_notepad_detection(self):
        intent = RuleBasedIntentParser.parse("Please open notepad for me")
        self.assertEqual(intent.name, "OPEN_APP")
        self.assertEqual(intent.parameters.get("app_name"), "notepad")

    def test_calculator_detection(self):
        intent = RuleBasedIntentParser.parse("Launch calculator app")
        self.assertEqual(intent.name, "OPEN_APP")
        self.assertEqual(intent.parameters.get("app_name"), "calculator")

    def test_current_news_is_not_misclassified_as_time(self):
        intent = RuleBasedIntentParser.parse("What happened in AI news today?")
        self.assertEqual(intent.name, "UNKNOWN")

    def test_explanation_about_notepad_does_not_launch_it(self):
        intent = RuleBasedIntentParser.parse("Explain how Notepad stores text")
        self.assertEqual(intent.name, "UNKNOWN")

    def test_website_detection(self):
        intent = RuleBasedIntentParser.parse("Open google in my browser")
        self.assertEqual(intent.name, "OPEN_WEBSITE")
        self.assertEqual(intent.parameters.get("url"), "https://www.google.com")

    def test_explicit_url_is_preserved_for_executor_allowlist_validation(self):
        url = "https://www.github.com/openai/example?tab=readme"
        intent = RuleBasedIntentParser.parse(f"Open {url}")
        self.assertEqual(intent.name, "OPEN_WEBSITE")
        self.assertEqual(intent.parameters.get("url"), url)

if __name__ == '__main__':
    unittest.main()
