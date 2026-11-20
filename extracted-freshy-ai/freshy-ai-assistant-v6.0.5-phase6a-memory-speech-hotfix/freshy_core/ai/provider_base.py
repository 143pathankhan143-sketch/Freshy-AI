from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from ai.schemas import ChatMessage, ProviderResponse


class BaseAIProvider(ABC):
    @property
    @abstractmethod
    def provider_name(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def model_name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def is_configured(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def generate(
        self,
        messages: List[ChatMessage],
        system_instruction: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> ProviderResponse:
        raise NotImplementedError

    @abstractmethod
    def health_check(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def supports_tools(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def normalize_error(self, exc: Exception) -> str:
        raise NotImplementedError
