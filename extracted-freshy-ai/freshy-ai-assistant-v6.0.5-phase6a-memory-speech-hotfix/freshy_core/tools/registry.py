import logging
from typing import Any, Callable, Dict, List, Optional

from pydantic import ValidationError

from ai.schemas import ToolResult
from ai.web_search_service import WebSearchService
from executor import CommandExecutor
from tools.schemas import (
    OpenApplicationArguments,
    OpenWebsiteArguments,
    TimeDateArguments,
    ToolArguments,
    ToolDefinition,
    WebSearchArguments,
)

logger = logging.getLogger("ToolRegistry")
ToolHandler = Callable[[ToolArguments], ToolResult]


class ToolRegistry:
    def __init__(
        self,
        search_service: Optional[WebSearchService] = None,
        executor: Optional[CommandExecutor] = None,
    ):
        self._executor = executor or CommandExecutor()
        self._search_service = search_service or WebSearchService()
        self._tools: Dict[str, ToolDefinition] = {}
        self._handlers: Dict[str, ToolHandler] = {}
        self._register_defaults()

    def register_tool(self, definition: ToolDefinition, handler: ToolHandler) -> None:
        if definition.name in self._tools:
            raise ValueError(f"Tool '{definition.name}' is already registered.")
        self._tools[definition.name] = definition
        self._handlers[definition.name] = handler

    def list_tools(self) -> List[ToolDefinition]:
        return list(self._tools.values())

    def provider_tools(self, include_web_search: bool = True) -> List[Dict[str, Any]]:
        return [
            definition.provider_schema()
            for definition in self._tools.values()
            if include_web_search or definition.name != "web_search"
        ]

    def execute_tool(self, name: str, arguments: Dict[str, Any]) -> ToolResult:
        definition = self._tools.get(str(name or ""))
        handler = self._handlers.get(str(name or ""))
        if definition is None or handler is None:
            return ToolResult(
                success=False,
                error=f"Security Block: Tool '{name}' is not registered or permitted.",
                metadata={"action_executed": False},
            )
        if not isinstance(arguments, dict):
            return ToolResult(
                success=False,
                error="Security Block: Tool arguments must be a JSON object.",
                metadata={"action_executed": False},
            )
        try:
            validated = definition.arguments_model.model_validate(arguments)
        except ValidationError:
            return ToolResult(
                success=False,
                error=f"Security Block: Invalid arguments for tool '{definition.name}'.",
                metadata={"action_executed": False},
            )
        try:
            logger.info("Executing validated tool '%s'.", definition.name)
            return handler(validated)
        except Exception:
            logger.exception("Registered tool '%s' failed safely.", definition.name)
            return ToolResult(
                success=False,
                error=f"Tool '{definition.name}' could not be completed.",
                metadata={"action_executed": False},
            )

    def _register_defaults(self) -> None:
        self.register_tool(
            ToolDefinition(
                name="get_time_date",
                description="Get the current local date and time.",
                arguments_model=TimeDateArguments,
            ),
            self._handle_time_date,
        )
        self.register_tool(
            ToolDefinition(
                name="open_application",
                description="Open an allowlisted application: notepad or calculator.",
                arguments_model=OpenApplicationArguments,
            ),
            self._handle_open_application,
        )
        self.register_tool(
            ToolDefinition(
                name="open_website",
                description=(
                    "Open an allowlisted website. Only Google, YouTube, GitHub and Wikipedia "
                    "domains are permitted."
                ),
                arguments_model=OpenWebsiteArguments,
            ),
            self._handle_open_website,
        )
        self.register_tool(
            ToolDefinition(
                name="web_search",
                description="Search the public web for live or current information.",
                arguments_model=WebSearchArguments,
            ),
            self._handle_web_search,
        )

    def _handle_time_date(self, _: ToolArguments) -> ToolResult:
        success, reply, details = self._executor.execute_intent("TIME_DATE", {})
        return ToolResult(
            success=success,
            output=reply if success else "",
            error=None if success else reply,
            metadata={**details, "action_executed": success},
        )

    def _handle_open_application(self, args: ToolArguments) -> ToolResult:
        assert isinstance(args, OpenApplicationArguments)
        success, reply, details = self._executor.execute_intent(
            "OPEN_APP", {"app_name": args.app_name}
        )
        actually_executed = success and details.get("status") != "simulated_non_windows"
        return ToolResult(
            success=success,
            output=reply if success else "",
            error=None if success else reply,
            metadata={**details, "action_executed": actually_executed},
        )

    def _handle_open_website(self, args: ToolArguments) -> ToolResult:
        assert isinstance(args, OpenWebsiteArguments)
        success, reply, details = self._executor.execute_intent(
            "OPEN_WEBSITE", {"url": args.url}
        )
        return ToolResult(
            success=success,
            output=reply if success else "",
            error=None if success else reply,
            metadata={**details, "action_executed": success},
        )

    def _handle_web_search(self, args: ToolArguments) -> ToolResult:
        assert isinstance(args, WebSearchArguments)
        results = self._search_service.search(args.query)
        if not results:
            reason = self._search_service.last_error or "no_results"
            return ToolResult(
                success=False,
                error=f"Web search could not return results ({reason}).",
                metadata={"action_executed": False, "sources": [], "search_error": reason},
            )
        sources = [item.model_dump() for item in results]
        context = "\n\n".join(
            f"Source {index}:\nTitle: {item.title}\nURL: {item.url}\nSnippet: {item.content}"
            for index, item in enumerate(results, start=1)
        )
        return ToolResult(
            success=True,
            output=context,
            metadata={"action_executed": True, "sources": sources},
        )
