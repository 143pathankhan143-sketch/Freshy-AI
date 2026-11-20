import json
import logging
import re
from typing import Any, Dict, List, Optional

import requests

from ai.provider_base import BaseAIProvider
from ai.schemas import ChatMessage, ProviderResponse, ToolRequest

logger = logging.getLogger("OpenAICompatibleProvider")

_SECRET_PATTERN = re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]+")


def _safe_error_text(value: object, limit: int = 240) -> str:
    text = _SECRET_PATTERN.sub(r"\1[REDACTED]", str(value))
    return text[:limit]


def _normalize_content(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: List[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                value = item.get("text") or item.get("content")
                if isinstance(value, str):
                    parts.append(value)
        return "\n".join(parts).strip()
    return ""


class OpenAICompatibleProvider(BaseAIProvider):
    def __init__(
        self,
        name: str,
        base_url: str,
        api_key: str,
        model_name: str,
        timeout: int = 25,
        max_tokens: int = 1200,
        temperature: float = 0.3,
        session: Optional[requests.Session] = None,
    ):
        self._name = name.strip().lower()
        self.base_url = base_url.strip()
        self.api_key = api_key.strip()
        self._model_name = model_name.strip()
        self.timeout = timeout
        self.max_tokens = max_tokens
        self.temperature = temperature
        self._session = session or requests.Session()

    @property
    def provider_name(self) -> str:
        return self._name

    @property
    def model_name(self) -> str:
        return self._model_name

    def is_configured(self) -> bool:
        dummy_keys = {
            "",
            "my_groq_api_key",
            "my_mistral_api_key",
            "my_sambanova_api_key",
            "my_gemini_api_key",
        }
        key = self.api_key.lower()
        return bool(key and key not in dummy_keys and self.model_name)

    def supports_tools(self) -> bool:
        return True

    def health_check(self) -> bool:
        # Avoid spending credits for status checks. "Configured" is the safe local health signal.
        return self.is_configured()

    def normalize_error(self, exc: Exception) -> str:
        if isinstance(exc, requests.exceptions.Timeout):
            return "timeout"
        if isinstance(exc, requests.exceptions.ConnectionError):
            return "network_error"
        if isinstance(exc, requests.exceptions.JSONDecodeError):
            return "malformed_response"

        if isinstance(exc, requests.exceptions.HTTPError) and exc.response is not None:
            status = exc.response.status_code
            if status == 401:
                return "authentication_error"
            if status == 403:
                return "permission_error"
            if status == 429:
                return "rate_limited"
            if status == 404:
                return "invalid_model"
            if status in {400, 409, 422}:
                body = _safe_error_text(exc.response.text).lower()
                return "invalid_model" if "model" in body else "invalid_request"
            if status >= 500:
                return "provider_unavailable"

        lowered = str(exc).lower()
        if "api key" in lowered or "unauthorized" in lowered:
            return "authentication_error"
        if "rate limit" in lowered or "429" in lowered:
            return "rate_limited"
        if "timeout" in lowered:
            return "timeout"
        if "model" in lowered:
            return "invalid_model"
        return "unknown_provider_error"

    def generate(
        self,
        messages: List[ChatMessage],
        system_instruction: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> ProviderResponse:
        if not self.is_configured():
            return ProviderResponse(
                provider_name=self.provider_name,
                model_name=self.model_name,
                success=False,
                error_code="missing_key",
                error_message="Provider is not configured.",
            )

        formatted_messages: List[Dict[str, str]] = []
        if system_instruction:
            formatted_messages.append({"role": "system", "content": system_instruction})
        for message in messages:
            # Freshy stores tool outcomes as bounded text history without the
            # provider-specific tool_call_id required by OpenAI-compatible APIs.
            # Re-send that text as a user context message rather than emitting an
            # invalid standalone ``role=tool`` message.
            role = message.role if message.role in {"user", "assistant", "system"} else "user"
            formatted_messages.append({"role": role, "content": message.content})

        url = self.base_url.rstrip("/")
        if not url.endswith("/chat/completions"):
            url += "/chat/completions"

        payload: Dict[str, Any] = {
            "model": self.model_name,
            "messages": formatted_messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        try:
            logger.info("Sending request to %s using model %s", self.provider_name, self.model_name)
            response = self._session.post(
                url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
            choices = data.get("choices") if isinstance(data, dict) else None
            if not isinstance(choices, list) or not choices:
                return ProviderResponse(
                    provider_name=self.provider_name,
                    model_name=self.model_name,
                    success=False,
                    error_code="malformed_response",
                    error_message="Provider returned no choices.",
                )

            message_data = choices[0].get("message", {}) if isinstance(choices[0], dict) else {}
            content = _normalize_content(message_data.get("content"))
            parsed_calls: List[ToolRequest] = []
            native_calls = message_data.get("tool_calls", [])
            if isinstance(native_calls, list):
                for call in native_calls:
                    if not isinstance(call, dict):
                        continue
                    function = call.get("function", {})
                    if not isinstance(function, dict):
                        continue
                    name = function.get("name")
                    raw_arguments = function.get("arguments", {})
                    try:
                        arguments = json.loads(raw_arguments) if isinstance(raw_arguments, str) else raw_arguments
                    except (TypeError, json.JSONDecodeError):
                        arguments = {}
                    if isinstance(name, str) and isinstance(arguments, dict):
                        parsed_calls.append(
                            ToolRequest(
                                name=name,
                                arguments=arguments,
                                call_id=str(call.get("id") or "") or None,
                            )
                        )

            if not content and not parsed_calls:
                return ProviderResponse(
                    provider_name=self.provider_name,
                    model_name=self.model_name,
                    success=False,
                    error_code="malformed_response",
                    error_message="Provider returned an empty response.",
                )

            return ProviderResponse(
                content=content,
                tool_calls=parsed_calls,
                provider_name=self.provider_name,
                model_name=self.model_name,
                success=True,
            )
        except Exception as exc:
            code = self.normalize_error(exc)
            safe_error = _safe_error_text(exc)
            logger.warning("Provider %s failed (%s): %s", self.provider_name, code, safe_error)
            return ProviderResponse(
                provider_name=self.provider_name,
                model_name=self.model_name,
                success=False,
                error_code=code,
                error_message=safe_error,
            )
