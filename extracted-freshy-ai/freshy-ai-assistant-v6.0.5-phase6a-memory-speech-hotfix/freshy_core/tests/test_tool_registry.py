import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ai.schemas import SearchResult
from tools.registry import ToolRegistry


class FakeSearch:
    last_error = None

    def is_configured(self):
        return True

    def search(self, query):
        return [SearchResult(title="Source", url="https://example.com", content="Fact")]


class ToolRegistryTests(unittest.TestCase):
    def setUp(self):
        self.registry = ToolRegistry(search_service=FakeSearch())

    def test_unknown_and_shell_like_tools_are_rejected(self):
        for name in ("shell", "powershell", "delete_file", "run_command"):
            result = self.registry.execute_tool(name, {"command": "whoami"})
            self.assertFalse(result.success)
            self.assertIn("Security Block", result.error)

    def test_extra_arguments_and_unallowlisted_app_are_rejected(self):
        extra = self.registry.execute_tool(
            "open_application", {"app_name": "notepad", "command": "calc.exe"}
        )
        unsafe = self.registry.execute_tool(
            "open_application", {"app_name": "C:\\Windows\\System32\\cmd.exe"}
        )
        self.assertFalse(extra.success)
        self.assertFalse(unsafe.success)

    def test_unallowlisted_domain_is_rejected(self):
        result = self.registry.execute_tool(
            "open_website", {"url": "https://google.com.evil.example"}
        )
        self.assertFalse(result.success)
        self.assertIn("Security Block", result.error)

    def test_allowlisted_app_calls_existing_executor(self):
        with patch("subprocess.Popen"):
            result = self.registry.execute_tool("open_application", {"app_name": "notepad"})
        self.assertTrue(result.success)
        self.assertIn("Notepad", result.output)

    def test_web_search_returns_source_metadata(self):
        result = self.registry.execute_tool("web_search", {"query": "latest"})
        self.assertTrue(result.success)
        self.assertEqual(result.metadata["sources"][0]["title"], "Source")


if __name__ == "__main__":
    unittest.main()
