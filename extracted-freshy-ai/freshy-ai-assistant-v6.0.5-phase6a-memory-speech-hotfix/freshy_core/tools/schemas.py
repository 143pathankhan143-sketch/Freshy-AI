from typing import Any, Dict, Literal, Type

from pydantic import BaseModel, ConfigDict, Field


class ToolArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TimeDateArguments(ToolArguments):
    pass


class OpenApplicationArguments(ToolArguments):
    app_name: Literal["notepad", "calculator"]


class OpenWebsiteArguments(ToolArguments):
    url: str = Field(min_length=1, max_length=2000)


class WebSearchArguments(ToolArguments):
    query: str = Field(min_length=1, max_length=500)


class ToolDefinition(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    description: str
    arguments_model: Type[ToolArguments]

    def provider_schema(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.arguments_model.model_json_schema(),
            },
        }
