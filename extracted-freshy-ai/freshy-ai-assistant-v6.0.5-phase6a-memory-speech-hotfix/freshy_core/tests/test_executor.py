import unittest
import sys
import os
from unittest.mock import patch

# Add parent directory to sys.path for test imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from executor import CommandExecutor

class TestCommandExecutor(unittest.TestCase):

    def setUp(self):
        self.executor = CommandExecutor()

    def test_greeting_intent(self):
        success, reply, details = self.executor.execute_intent("GREETING", {})
        self.assertTrue(success)
        self.assertIn("Freshy", reply)
        self.assertEqual(details["action"], "GREETING")

    def test_time_date_intent(self):
        success, reply, details = self.executor.execute_intent("TIME_DATE", {})
        self.assertTrue(success)
        self.assertIn("current time is", reply.lower())
        self.assertIn("time", details)

    def test_allowlisted_open_notepad(self):
        with patch("executor.platform.system", return_value="Windows"), \
             patch("executor.subprocess.Popen") as mock_popen:
            success, reply, details = self.executor.execute_intent("OPEN_APP", {"app_name": "notepad"})
        self.assertTrue(success)
        self.assertIn("Notepad", reply)
        mock_popen.assert_called_once_with(["notepad.exe"])

    def test_block_unallowed_app(self):
        success, reply, details = self.executor.execute_intent("OPEN_APP", {"app_name": "cmd_prompt_hack"})
        self.assertFalse(success)
        self.assertIn("Security Block", reply)

    def test_allowed_domain_website(self):
        with patch("executor.webbrowser.open", return_value=True) as mock_open:
            success, reply, details = self.executor.execute_intent("OPEN_WEBSITE", {"url": "https://www.google.com"})
        self.assertTrue(success)
        self.assertIn("Opening", reply)
        mock_open.assert_called_once_with("https://www.google.com")

    def test_blocked_domain_website(self):
        success, reply, details = self.executor.execute_intent("OPEN_WEBSITE", {"url": "https://unsupported-malicious-domain.com"})
        self.assertFalse(success)
        self.assertIn("Security Block", reply)
        self.assertIn("unsupported-malicious-domain.com", reply)

    def test_deceptive_userinfo_url_is_blocked(self):
        success, reply, details = self.executor.execute_intent(
            "OPEN_WEBSITE",
            {"url": "https://www.google.com:443@unsupported-malicious-domain.com"},
        )
        self.assertFalse(success)
        self.assertIn("Security Block", reply)
        self.assertIn("unsupported-malicious-domain.com", reply)

    def test_empty_query_message(self):
        success, reply, details = self.executor.execute_intent("UNKNOWN", {"query": "   "})
        self.assertFalse(success)
        self.assertIn("empty", reply.lower())

if __name__ == '__main__':
    unittest.main()
