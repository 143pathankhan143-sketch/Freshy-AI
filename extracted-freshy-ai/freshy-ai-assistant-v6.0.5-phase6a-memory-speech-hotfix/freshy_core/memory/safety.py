from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class SafetyDecision:
    safe: bool
    reason: Optional[str] = None


_SECRET_PATTERNS = (
    re.compile(r"\b(?:api[_ -]?key|secret|password|passwd|otp|one[- ]time password|access[_ -]?token|refresh[_ -]?token|bearer token|private key)\b", re.I),
    re.compile(r"\bAIza[0-9A-Za-z_-]{20,}\b"),
    re.compile(r"\b(?:gsk_|sk-|hf_|tvly-|xox[baprs]-)[0-9A-Za-z_-]{12,}\b"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", re.I),
    re.compile(r"\b\d{6}\b.*\b(?:otp|code|verification)\b", re.I),
)

_PROMPT_INJECTION_PATTERNS = (
    re.compile(r"\bignore (?:all |the )?(?:previous|system|developer) instructions\b", re.I),
    re.compile(r"\boverride (?:the )?(?:system|safety|security)\b", re.I),
    re.compile(r"\breveal (?:the )?(?:system prompt|api key|secret|credentials)\b", re.I),
    re.compile(r"\b(?:run|execute) (?:cmd|powershell|shell|terminal command)\b", re.I),
)



def contains_secret(text: str) -> bool:
    """Return True when text resembles credentials or verification secrets."""
    value = str(text or "")
    return any(pattern.search(value) for pattern in _SECRET_PATTERNS)

def inspect_memory_text(text: str) -> SafetyDecision:
    value = str(text or "").strip()
    if not value:
        return SafetyDecision(False, "Memory text cannot be empty.")
    for pattern in _SECRET_PATTERNS:
        if pattern.search(value):
            return SafetyDecision(False, "Secrets, credentials and verification codes cannot be stored in memory.")
    for pattern in _PROMPT_INJECTION_PATTERNS:
        if pattern.search(value):
            return SafetyDecision(False, "Executable instructions or attempts to override Freshy safety cannot be stored as memory.")
    return SafetyDecision(True)
