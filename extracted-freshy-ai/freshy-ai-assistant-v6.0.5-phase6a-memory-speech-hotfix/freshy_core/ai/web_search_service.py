import logging
import re
from typing import List, Optional
from urllib.parse import urlparse

import requests

from ai.schemas import SearchResult
from config import config

logger = logging.getLogger("WebSearchService")
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _clean(value: object, limit: int) -> str:
    text = _CONTROL_CHARS.sub(" ", str(value or ""))
    text = " ".join(text.split())
    return text[:limit]


class WebSearchService:
    def __init__(
        self,
        api_key: Optional[str] = None,
        timeout: Optional[int] = None,
        max_results: Optional[int] = None,
        search_depth: Optional[str] = None,
        session: Optional[requests.Session] = None,
    ):
        self._api_key = (api_key if api_key is not None else config.TAVILY_API_KEY).strip()
        self.timeout = timeout or config.TAVILY_TIMEOUT_SECONDS
        self.max_results = max_results or config.TAVILY_MAX_RESULTS
        self.search_depth = search_depth or config.TAVILY_SEARCH_DEPTH
        self._session = session or requests.Session()
        self.last_error: Optional[str] = None

    def is_configured(self) -> bool:
        dummy = {"", "my_tavily_api_key", "my_tavily_api_key_here"}
        return self._api_key.lower() not in dummy

    def search(self, query: str) -> List[SearchResult]:
        self.last_error = None
        clean_query = _clean(query, 500)
        if not clean_query:
            self.last_error = "empty_query"
            return []
        if not self.is_configured():
            self.last_error = "missing_key"
            return []

        try:
            response = self._session.post(
                "https://api.tavily.com/search",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "query": clean_query,
                    "search_depth": self.search_depth,
                    "max_results": self.max_results,
                    "include_answer": False,
                    "include_images": False,
                    "include_raw_content": False,
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
            raw_results = payload.get("results", []) if isinstance(payload, dict) else []
            output: List[SearchResult] = []
            seen_urls: set[str] = set()
            for item in raw_results[: self.max_results]:
                if not isinstance(item, dict):
                    continue
                url = _clean(item.get("url"), 1000)
                parsed = urlparse(url)
                if parsed.scheme not in {"http", "https"} or not parsed.hostname or url in seen_urls:
                    continue
                seen_urls.add(url)
                score = item.get("score")
                try:
                    normalized_score = float(score) if score is not None else None
                except (TypeError, ValueError):
                    normalized_score = None
                output.append(
                    SearchResult(
                        title=_clean(item.get("title") or "Untitled source", 300),
                        url=url,
                        content=_clean(item.get("content"), 1500),
                        score=normalized_score,
                    )
                )
            return output
        except requests.exceptions.Timeout:
            self.last_error = "timeout"
        except requests.exceptions.ConnectionError:
            self.last_error = "network_error"
        except requests.exceptions.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else 0
            self.last_error = "authentication_error" if status in {401, 403} else "search_unavailable"
        except (ValueError, TypeError):
            self.last_error = "malformed_response"
        except Exception:
            self.last_error = "search_unavailable"
        logger.warning("Tavily search failed safely (%s).", self.last_error)
        return []
