import logging
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from ai.gemini_provider import GeminiProvider
from ai.openai_compatible_provider import OpenAICompatibleProvider
from ai.provider_base import BaseAIProvider
from ai.schemas import ChatMessage, ProviderResponse
from config import config

logger = logging.getLogger("ProviderRouter")
_TRANSIENT_ERRORS = {"rate_limited", "timeout", "network_error", "provider_unavailable"}
_FATAL_ERRORS = {
    "authentication_error",
    "permission_error",
    "missing_key",
    "invalid_model",
    "invalid_request",
}


class ProviderRouter:
    def __init__(
        self,
        providers: Optional[List[BaseAIProvider]] = None,
        provider_order: Optional[List[str]] = None,
        ai_enabled: Optional[bool] = None,
        max_retries: Optional[int] = None,
        cooldown_seconds: Optional[int] = None,
        time_fn: Callable[[], float] = time.time,
        sleep_fn: Callable[[float], None] = time.sleep,
    ):
        self.providers: Dict[str, BaseAIProvider] = {}
        if providers is None:
            providers = self._default_providers()
        for provider in providers:
            self.providers[provider.provider_name] = provider

        self.provider_order = list(provider_order or config.AI_PROVIDER_ORDER)
        self.ai_enabled = config.AI_ENABLED if ai_enabled is None else ai_enabled
        self.max_retries = config.AI_MAX_RETRIES if max_retries is None else max_retries
        self.cooldown_seconds = (
            config.AI_PROVIDER_COOLDOWN_SECONDS
            if cooldown_seconds is None
            else cooldown_seconds
        )
        self._time = time_fn
        self._sleep = sleep_fn
        self.cooldowns: Dict[str, float] = {}
        self._lock = threading.RLock()

    @staticmethod
    def _default_providers() -> List[BaseAIProvider]:
        common = {
            "timeout": config.AI_REQUEST_TIMEOUT_SECONDS,
            "max_tokens": config.AI_MAX_OUTPUT_TOKENS,
            "temperature": config.AI_TEMPERATURE,
        }
        return [
            OpenAICompatibleProvider(
                name="groq",
                base_url=config.GROQ_BASE_URL,
                api_key=config.GROQ_API_KEY,
                model_name=config.GROQ_MODEL,
                **common,
            ),
            OpenAICompatibleProvider(
                name="mistral",
                base_url=config.MISTRAL_BASE_URL,
                api_key=config.MISTRAL_API_KEY,
                model_name=config.MISTRAL_MODEL,
                **common,
            ),
            GeminiProvider(
                api_key=config.GEMINI_API_KEY,
                model_name=config.GEMINI_MODEL,
                **common,
            ),
            OpenAICompatibleProvider(
                name="sambanova",
                base_url=config.SAMBANOVA_BASE_URL,
                api_key=config.SAMBANOVA_API_KEY,
                model_name=config.SAMBANOVA_MODEL,
                **common,
            ),
        ]

    def has_available_provider(self) -> bool:
        """Return whether at least one configured provider is not in cooldown."""
        if not self.ai_enabled:
            return False
        seen: set[str] = set()
        for name in self.provider_order:
            if name in seen:
                continue
            seen.add(name)
            provider = self.providers.get(name)
            if (
                provider is not None
                and provider.is_configured()
                and not self.is_provider_cooldown(name)
            ):
                return True
        return False

    def is_provider_cooldown(self, name: str) -> bool:
        with self._lock:
            until = self.cooldowns.get(name, 0.0)
            if until and until <= self._time():
                self.cooldowns.pop(name, None)
                return False
            return bool(until)

    def trigger_cooldown(self, name: str) -> None:
        with self._lock:
            self.cooldowns[name] = self._time() + max(1, self.cooldown_seconds)
        logger.warning("Provider '%s' entered temporary cooldown.", name)

    def _execute_with_retry(
        self,
        provider: BaseAIProvider,
        messages: List[ChatMessage],
        system_instruction: Optional[str],
        tools: Optional[List[Dict[str, Any]]],
    ) -> ProviderResponse:
        attempts = 0
        while True:
            response = provider.generate(messages, system_instruction, tools)
            if response.success or response.error_code in _FATAL_ERRORS:
                return response
            if response.error_code not in _TRANSIENT_ERRORS or attempts >= self.max_retries:
                return response
            attempts += 1
            self._sleep(min(0.25 * attempts, 1.0))

    def route_request(
        self,
        messages: List[ChatMessage],
        system_instruction: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Tuple[ProviderResponse, List[Dict[str, Any]]]:
        fallback_chain: List[Dict[str, Any]] = []
        if not self.ai_enabled:
            return (
                ProviderResponse(
                    provider_name="none",
                    model_name="",
                    success=False,
                    error_code="ai_disabled",
                    error_message="AI routing is disabled.",
                ),
                fallback_chain,
            )

        seen: set[str] = set()
        for name in self.provider_order:
            if name in seen:
                continue
            seen.add(name)
            provider = self.providers.get(name)
            if provider is None:
                fallback_chain.append({"provider": name, "status": "unsupported_provider"})
                continue
            if not provider.is_configured():
                fallback_chain.append({"provider": name, "status": "missing_key"})
                continue
            if self.is_provider_cooldown(name):
                fallback_chain.append({"provider": name, "status": "cooldown"})
                continue

            response = self._execute_with_retry(provider, messages, system_instruction, tools)
            status = "success" if response.success else (response.error_code or "failed")
            fallback_chain.append({"provider": name, "status": status})
            if response.success:
                return response, fallback_chain
            if response.error_code in _TRANSIENT_ERRORS:
                self.trigger_cooldown(name)

        return (
            ProviderResponse(
                provider_name="none",
                model_name="",
                success=False,
                error_code="all_providers_failed",
                error_message="No configured AI provider completed the request.",
            ),
            fallback_chain,
        )

    def status(self) -> Dict[str, Any]:
        providers: Dict[str, Any] = {}
        now = self._time()
        for name, provider in self.providers.items():
            with self._lock:
                remaining = max(0, int(self.cooldowns.get(name, 0.0) - now))
            providers[name] = {
                "configured": provider.is_configured(),
                "model": provider.model_name,
                "cooldown_active": remaining > 0,
                "cooldown_remaining_seconds": remaining,
            }
        return {
            "ai_enabled": self.ai_enabled,
            "provider_order": self.provider_order,
            "providers": providers,
        }
