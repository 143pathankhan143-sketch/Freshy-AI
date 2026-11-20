from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urlparse

try:
    from tools.registry import ToolRegistry
except ImportError:
    from freshy_core.tools.registry import ToolRegistry

logger = logging.getLogger("FreshyLiveTools")


class LiveToolBridge:
    """Maps Gemini Live function calls to Freshy's existing validated registry."""

    def __init__(self, registry: Optional[ToolRegistry] = None, memory_service: Optional[Any] = None) -> None:
        self.registry = registry or ToolRegistry()
        self.memory_service = memory_service
        self._cancelled_ids: set[str] = set()

    def declarations(self) -> List[Dict[str, Any]]:
        declarations: List[Dict[str, Any]] = []
        for definition in self.registry.list_tools():
            declarations.append({
                "name": definition.name,
                "description": definition.description,
                "parameters": definition.arguments_model.model_json_schema(),
            })
        if self.memory_service is not None:
            declarations.extend([
                {
                    "name": "memory_control",
                    "description": (
                        "Handle an explicit user request to remember, forget, list, or confirm a memory. "
                        "Pass the user's exact memory-related sentence. The local privacy filter and confirmation policy remain authoritative."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {"message": {"type": "string", "maxLength": 2000}},
                        "required": ["message"],
                        "additionalProperties": False,
                    },
                },
                {
                    "name": "memory_lookup",
                    "description": "Retrieve a small relevant set of user-approved memories for the current question.",
                    "parameters": {
                        "type": "object",
                        "properties": {"query": {"type": "string", "maxLength": 2000}},
                        "required": ["query"],
                        "additionalProperties": False,
                    },
                },
            ])
        return declarations

    def cancel(self, call_ids: Iterable[str]) -> None:
        self._cancelled_ids.update(str(item) for item in call_ids)

    @staticmethod
    def _friendly_action_name(name: str, args: Dict[str, Any]) -> str:
        if name == "open_application":
            app = str(args.get("app_name", "application") or "application")
            return app.replace("_", " ").strip().title() or "Application"
        if name == "open_website":
            raw_url = str(args.get("url", "") or "").strip()
            parsed = urlparse(raw_url if "://" in raw_url else f"https://{raw_url}")
            hostname = (parsed.hostname or "").lower().removeprefix("www.")
            known = {
                "google.com": "Google",
                "youtube.com": "YouTube",
                "github.com": "GitHub",
                "wikipedia.org": "Wikipedia",
            }
            if hostname in known:
                return known[hostname]
            if hostname:
                label = hostname.split(".")[0].replace("-", " ").strip()
                return label.title() if label else "Website"
            return "Website"
        return "Action"

    @classmethod
    def _safe_action_payload(
        cls, name: str, args: Dict[str, Any], payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        if name not in {"open_application", "open_website"}:
            return payload
        safe = dict(payload)
        target = cls._friendly_action_name(name, args)
        if bool(payload.get("success")):
            safe["output"] = f"{target} is open."
            safe["error"] = None
        else:
            safe["output"] = "The requested action was not completed."
            safe["error"] = "The requested action was not completed."
        return safe

    async def execute(self, function_call: Any) -> Dict[str, Any]:
        call_id = str(getattr(function_call, "id", "") or "")
        name = str(getattr(function_call, "name", "") or "")
        args = getattr(function_call, "args", None)
        if args is None:
            args = getattr(function_call, "arguments", {})
        if hasattr(args, "model_dump"):
            args = args.model_dump()
        if not isinstance(args, dict):
            args = {}
        if call_id and call_id in self._cancelled_ids:
            return {"id": call_id, "name": name, "response": {"success": False, "error": "cancelled"}}
        if name == "memory_control" and self.memory_service is not None:
            message = str(args.get("message", "") or "").strip()
            if not message:
                return {"id": call_id, "name": name, "response": {"success": False, "error": "Memory message is required.", "metadata": {"action_executed": False}}}
            result = await asyncio.to_thread(
                self.memory_service.process_control_message,
                "live-voice-session",
                message,
            )
            if result is None:
                return {"id": call_id, "name": name, "response": {"success": False, "error": "The request was not a supported memory-control command.", "metadata": {"action_executed": False}}}
            return {
                "id": call_id,
                "name": name,
                "response": {
                    "success": bool(result.success),
                    "output": result.reply,
                    "error": result.error_code,
                    "metadata": {
                        "action_executed": bool(result.success),
                        "memory_count": result.memory_count,
                        "pending_confirmation": result.pending_confirmation,
                    },
                },
            }
        if name == "memory_lookup" and self.memory_service is not None:
            query = str(args.get("query", "") or "").strip()
            recall = await asyncio.to_thread(self.memory_service.recall, query)
            return {
                "id": call_id,
                "name": name,
                "response": {
                    "success": True,
                    "output": recall.context or "No relevant permanent memory was found.",
                    "error": None,
                    "metadata": {"action_executed": False, "memory_count": len(recall.records)},
                },
            }
        result = await asyncio.to_thread(self.registry.execute_tool, name, args)
        payload = {
            "success": result.success,
            "output": result.output,
            "error": result.error,
            "metadata": result.metadata,
        }
        payload = self._safe_action_payload(name, args, payload)
        return {"id": call_id, "name": name, "response": payload}
