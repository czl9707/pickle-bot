"""Base skill interface and decorator."""

from abc import ABC, abstractmethod
from typing import Any, Callable


class BaseSkill(ABC):
    """
    Abstract base class for all skills.

    Skills are pluggable capabilities that the agent can use.
    They should define name, description, and parameters for function calling.
    """

    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema for function calling

    @abstractmethod
    async def execute(self, **kwargs: Any) -> str:
        """
        Execute the skill.

        Args:
            **kwargs: Arguments for the skill

        Returns:
            String result of the skill execution
        """

    def get_tool_schema(self) -> dict[str, Any]:
        """
        Get the tool/function schema for LiteLLM function calling.

        Returns:
            Tool schema dictionary
        """
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


def skill(name: str, description: str, parameters: dict[str, Any]) -> Callable:
    """
    Decorator to register a function as a skill.

    The decorated function will be wrapped in a FunctionSkill class.

    Args:
        name: Name of the skill
        description: Description of what the skill does
        parameters: JSON Schema for the skill's parameters

    Returns:
        Decorator function

    Example:
        ```python
        @skill(
            name="get_weather",
            description="Get the current weather for a location",
            parameters={
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "The city name",
                    }
                },
                "required": ["location"],
            },
        )
        async def get_weather(location: str) -> str:
            return f"Weather in {location}: Sunny, 72°F"
        ```
    """

    def decorator(func: Callable) -> "FunctionSkill":
        return FunctionSkill(name, description, parameters, func)

    return decorator


class FunctionSkill(BaseSkill):
    """
    A skill created from a function using the @skill decorator.
    """

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


# Import at end to avoid circular dependency
import asyncio
