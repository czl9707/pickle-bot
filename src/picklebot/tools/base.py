"""Base tool interface and decorator."""

import asyncio
from abc import ABC, abstractmethod
from typing import Any, Callable


class BaseTool(ABC):
    """Abstract base class for all tools."""

    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema for function calling

    @abstractmethod
    async def execute(self, **kwargs: Any) -> str:
        """Execute the tool."""

    def get_tool_schema(self) -> dict[str, Any]:
        """Get the tool/function schema for LiteLLM."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


def tool(name: str, description: str, parameters: dict[str, Any]) -> Callable:
    """Decorator to register a function as a tool."""

    def decorator(func: Callable) -> "FunctionTool":
        return FunctionTool(name, description, parameters, func)

    return decorator


class FunctionTool(BaseTool):
    """A tool created from a function using the @tool decorator."""

    def __init__(
        self,
        name: str,
        description: str,
        parameters: dict[str, Any],
        func: Callable,
    ):
        self.name = name
        self.description = description
        self.parameters = parameters
        self._func = func

    async def execute(self, **kwargs: Any) -> str:
        """Execute the underlying function."""
        result = self._func(**kwargs)
        if asyncio.iscoroutine(result):
            result = await result
        return str(result)
