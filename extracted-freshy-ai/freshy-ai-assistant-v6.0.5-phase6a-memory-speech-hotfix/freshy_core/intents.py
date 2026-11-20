import re
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class Intent(BaseModel):
    name: str  # GREETING, TIME_DATE, OPEN_APP, OPEN_WEBSITE, UNKNOWN
    confidence: float
    parameters: Dict[str, Any] = Field(default_factory=dict)
    explanation: Optional[str] = None


class RuleBasedIntentParser:
    """Fast deterministic parser for Freshy's small local allowlist."""

    @staticmethod
    def parse(text: str) -> Intent:
        clean_text = str(text or "").strip().lower()

        # VoiceInputService normally removes this wake prefix. Keeping the same
        # behavior here makes typed/API commands deterministic as well.
        if clean_text.startswith("hello freshy "):
            clean_text = clean_text[len("hello freshy ") :].strip()

        # Capture a raw URL before punctuation normalization removes :// and /.
        raw_url_match = re.fullmatch(
            r"(?:please\s+)?(?:open|go\s+to|launch|visit|kholo)\s+"
            r"(?P<url>https?://\S+)(?:\s+in\s+my\s+browser)?",
            clean_text,
            flags=re.IGNORECASE,
        )
        if raw_url_match:
            url = raw_url_match.group("url")
            return Intent(
                name="OPEN_WEBSITE",
                confidence=0.98,
                parameters={"url": url, "target": url},
                explanation="Detected an explicit URL for local allowlist validation.",
            )

        normalized = re.sub(r"[^a-z0-9'\s]", " ", clean_text)
        normalized = re.sub(r"\s+", " ", normalized).strip()

        # Keep greeting recognition command-shaped so a question about Freshy
        # itself is not mistaken for a greeting.
        if re.fullmatch(
            r"(?:hello+|h+i+|h+y+|he+y+|heuy|greetings|good morning|good evening)"
            r"(?: freshy)?(?: how are you)?|"
            r"namaste(?: kaise ho)?|freshy|who are you|kaise ho|kya haal(?: hai)?",
            normalized,
        ):
            return Intent(
                name="GREETING",
                confidence=0.95,
                parameters={"raw_text": text},
                explanation="Detected greeting keyword.",
            )

        # Avoid broad keywords such as 'today': 'AI news today' must reach the
        # current-information path instead of returning the local clock.
        if re.fullmatch(
            r"(?:what(?: is|'s)? the current time(?: right now| now)?|"
            r"what time is it(?: right now| now)?|current time|time|clock|"
            r"kya time(?: hai)?|time kya(?: hai)?|kitne baje(?: hain)?|"
            r"what(?: is|'s)? (?:today'?s |the )?date|what date is it|"
            r"current date|date|what day is it|aaj kya date(?: hai)?)",
            normalized,
        ):
            return Intent(
                name="TIME_DATE",
                confidence=0.95,
                parameters={},
                explanation="Detected time/date query.",
            )

        if re.fullmatch(
            r"(?:(?:please )?(?:open|launch|start) notepad(?: app)?(?: for me)?|"
            r"notepad(?: kholo| open| chalu)?)",
            normalized,
        ):
            return Intent(
                name="OPEN_APP",
                confidence=0.98,
                parameters={"app_name": "notepad"},
                explanation="Detected open Notepad command.",
            )

        if re.fullmatch(
            r"(?:(?:please )?(?:open|launch|start) (?:calculator|calc)(?: app)?(?: for me)?|"
            r"(?:calculator|calc)(?: kholo| open)?)",
            normalized,
        ):
            return Intent(
                name="OPEN_APP",
                confidence=0.98,
                parameters={"app_name": "calculator"},
                explanation="Detected open Calculator command.",
            )

        # Explicitly route common unsafe launch requests to the local executor so
        # it can reject them without spending an AI token.
        unsafe_app_match = re.fullmatch(
            r"(?:please )?(?:open|launch|start|kholo) "
            r"(?P<app>command prompt|cmd|powershell|terminal|registry editor|regedit)(?: app)?",
            normalized,
        )
        if unsafe_app_match:
            return Intent(
                name="OPEN_APP",
                confidence=0.99,
                parameters={"app_name": unsafe_app_match.group("app")},
                explanation="Detected an app launch request for local allowlist validation.",
            )

        prefix_web = re.fullmatch(
            r"(?:please )?(?:open|go to|launch|visit|kholo) "
            r"(?P<target>google|youtube|github|wikipedia|website|browser)"
            r"(?: in my browser)?",
            normalized,
        )
        suffix_web = re.fullmatch(
            r"(?P<target>google|youtube|github|wikipedia|website|browser) "
            r"(?:kholo|open|launch|visit)",
            normalized,
        )
        web_match = prefix_web or suffix_web
        if web_match:
            target = web_match.group("target")
            known_urls = {
                "google": "https://www.google.com",
                "youtube": "https://www.youtube.com",
                "github": "https://www.github.com",
                "wikipedia": "https://www.wikipedia.org",
                "website": "https://www.google.com",
                "browser": "https://www.google.com",
            }
            return Intent(
                name="OPEN_WEBSITE",
                confidence=0.95,
                parameters={"url": known_urls[target], "target": target},
                explanation="Detected open website command.",
            )

        # Generic domains are still classified locally solely so CommandExecutor
        # can apply its domain allowlist. No browser action occurs unless allowed.
        generic_site_match = re.fullmatch(
            r"(?:please )?(?:open|visit|go to|kholo) "
            r"(?P<name>[a-z0-9_-]+)(?: site| website)",
            normalized,
        )
        if generic_site_match:
            site_name = generic_site_match.group("name")
            return Intent(
                name="OPEN_WEBSITE",
                confidence=0.9,
                parameters={"url": f"https://{site_name}.com", "target": site_name},
                explanation="Detected a website request for local domain allowlist validation.",
            )

        return Intent(
            name="UNKNOWN",
            confidence=0.5,
            parameters={"query": text},
            explanation="No matching rule-based intent found.",
        )
