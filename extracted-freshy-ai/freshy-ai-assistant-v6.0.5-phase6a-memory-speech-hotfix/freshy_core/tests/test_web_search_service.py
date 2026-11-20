import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ai.web_search_service import WebSearchService


class FakeResponse:
    status_code = 200

    def raise_for_status(self):
        return None

    def json(self):
        return {
            "results": [
                {
                    "title": "  Official\x00 source  ",
                    "url": "https://example.com/release",
                    "content": "x" * 2000,
                    "score": "0.9",
                },
                {"title": "Bad", "url": "javascript:alert(1)", "content": "bad"},
            ]
        }


class FakeSession:
    def __init__(self):
        self.kwargs = None

    def post(self, *args, **kwargs):
        self.kwargs = kwargs
        return FakeResponse()


class WebSearchTests(unittest.TestCase):
    def test_uses_bearer_auth_and_sanitizes_results(self):
        session = FakeSession()
        service = WebSearchService(api_key="secret-value", session=session, max_results=5)
        results = service.search("latest release")
        self.assertEqual(len(results), 1)
        self.assertEqual(session.kwargs["headers"]["Authorization"], "Bearer secret-value")
        self.assertNotIn("api_key", session.kwargs["json"])
        self.assertLessEqual(len(results[0].content), 1500)
        self.assertNotIn("\x00", results[0].title)

    def test_missing_key_makes_no_request(self):
        session = FakeSession()
        service = WebSearchService(api_key="", session=session)
        self.assertEqual(service.search("latest"), [])
        self.assertEqual(service.last_error, "missing_key")
        self.assertIsNone(session.kwargs)


if __name__ == "__main__":
    unittest.main()
