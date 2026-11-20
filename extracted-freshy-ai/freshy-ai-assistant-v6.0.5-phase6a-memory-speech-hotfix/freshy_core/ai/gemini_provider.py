import logging
import re
from typing import Any, Dict, List, Optional

from ai.provider_base import BaseAIProvider
from ai.schemas import ChatMessage, ProviderResponse, ToolRequest
from config import config

logger = logging.getLogger("GeminiProvider")
_SECRET_PATTERN = re.compile(r"(?i)(api[_ -]?key|authorization|bearer)(\s*[:=]?\s*)[^\s,;]+")


def _safe_error(value: object, limit: int = 240) -> str:
    return _SECRET_PATTERN.sub(r"\1\2[REDACTED]", str(value))[:limit]


class GeminiProvider(BaseAIProvider):
    def __init__(
        self,
        api_key: str = "",
        model_name: str = "gemini-2.5-flash",
        timeout: int = 25,
        max_tokens: int = 1200,
        temperature: float = 0.3,
        client: Optional[Any] = None,
    ):
        self._api_key = (api_key or config.GEMINI_API_KEY).strip()
        self._model_name = model_name.strip()
        self.timeout = timeout
        self.max_tokens = max_tokens
        self.temperature = temperature
        self._client = client
        self._types: Optional[Any] = None
        self._initialization_error: Optional[str] = None

        # Lazy import is intentional: Freshy must start offline when Gemini is not configured.
        if self._client is None and self.is_configured():
            try:
                from google import genai
                from google.genai import types

                self._types = types
                self._client = genai.Client(
                    api_key=self._api_key,
                    http_options=types.HttpOptions(timeout=max(1, self.timeout) * 1000),
                )
            except Exception as exc:  # pragma: no cover - depends on optional SDK/runtime
                self._initialization_error = _safe_error(exc)
                logger.warning("Gemini client could not initialize: %s", self._initialization_error)

    @property
    def provider_name(self) -> str:
        return "gemini"

    @property
    def model_name(self) -> str:
        return self._model_name

    def is_configured(self) -> bool:
        dummy_keys = {"", "my_gemini_api_key", "my_gemini_api_key_here"}
        return bool(self._api_key.lower() not in dummy_keys and self.model_name)

    def supports_tools(self) -> bool:
        return True

    def health_check(self) -> bool:
        return self.is_configured() and self._client is not None

    def normalize_error(self, exc: Exception) -> str:
        text = str(exc).lower()
        if "api key" in text or "api_key" in text or "unauthorized" in text or "401" in text:
            return "authentication_error"
        if "permission" in text or "403" in text:
            return "permission_error"
        if "quota" in text or "rate limit" in text or "429" in text:
            return "rate_limited"
        if "timeout" in text or "deadline" in text:
            return "timeout"
        if "model" in text or "404" in text or "not found" in text:
            return "invalid_model"
        if "400" in text or "bad request" in text or "invalid argument" in text:
            return "invalid_request"
        if "unavailable" in text or "503" in text or "500" in text:
            return "provider_unavailable"
        return "unknown_provider_error"

    def _build_contents(self, messages: List[ChatMessage]) -> List[Dict[str, Any]]:
        contents: List[Dict[str, Any]] = []
        for message in messages:
            if message.role == "system":
                continue
            role = "model" if message.role == "assistant" else "user"
            contents.append({"role": role, "parts": [{"text": message.content}]})
        return contents

    def _build_tools(self, tools: Optional[List[Dict[str, Any]]]) -> Optional[List[Any]]:
        if not tools:
            return None
        declarations: List[Any] = []
        for tool in tools:
            function = tool.get("function", {}) if isinstance(tool, dict) else {}
            if not isinstance(function, dict) or not function.get("name"):
                continue
            declaration = {
                "name": function["name"],
                "description": function.get("description", ""),
                "parameters_json_schema": function.get(
                    "parameters", {"type": "object", "properties": {}}
                ),
            }
            if self._types is not None:
                declarations.append(self._types.FunctionDeclaration(**declaration))
            else:
                declarations.append(declaration)
        if not declarations:
            return None
        if self._types is not None:
            return [self._types.Tool(function_declarations=declarations)]
        return [{"function_declarations": declarations}]

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
        if self._client is None:
            return ProviderResponse(
                provider_name=self.provider_name,
                model_name=self.model_name,
                success=False,
                error_code="provider_unavailable",
                error_message=self._initialization_error or "Gemini client is unavailable.",
            )

        try:
            config_kwargs: Dict[str, Any] = {
                "temperature": self.temperature,
                "max_output_tokens": self.max_tokens,
            }
            if system_instruction:
                config_kwargs["system_instruction"] = system_instruction
            gemini_tools = self._build_tools(tools)
            if gemini_tools:
                config_kwargs["tools"] = gemini_tools

            generation_config: Any = config_kwargs
            if self._types is not None:
                generation_config = self._types.GenerateContentConfig(**config_kwargs)

            response = self._client.models.generate_content(
                model=self.model_name,
                contents=self._build_contents(messages),
                config=generation_config,
            )
            text_reply = str(getattr(response, "text", "") or "").strip()
            parsed_calls: List[ToolRequest] = []
            for call in list(getattr(response, "function_calls", None) or []):
                name = getattr(call, "name", None)
                arguments = getattr(call, "args", None) or {}
                if isinstance(name, str) and isinstance(arguments, dict):
                    parsed_calls.append(ToolRequest(name=name, arguments=arguments))

            if not text_reply and not parsed_calls:
                return ProviderResponse(
                    provider_name=self.provider_name,
                    model_name=self.model_name,
                    success=False,
                    error_code="malformed_response",
                    error_message="Provider returned an empty response.",
                )
            return ProviderResponse(
                content=text_reply,
                tool_calls=parsed_calls,
                provider_name=self.provider_name,
                model_name=self.model_name,
                success=True,
            )
        except Exception as exc:
            code = self.normalize_error(exc)
            safe = _safe_error(exc)
            logger.warning("Gemini failed (%s): %s", code, safe)
            return ProviderResponse(
                provider_name=self.provider_name,
                model_name=self.model_name,
                success=False,
                error_code=code,
                error_message=safe,
            )
