"""Tool registry."""

import logging
from collections.abc import Callable
from typing import Optional

from mobility_bench.tools.base import BaseTool

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Tool registry.

    Singleton pattern for managing registration and retrieval of all tools.
    """

    _instance: Optional["ToolRegistry"] = None
    _tools: dict[str, type[BaseTool] | Callable] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._tools = {}
        return cls._instance

    @classmethod
    def register(cls, name: str, tool: type[BaseTool] | Callable):
        """Register tool.

        Args:
            name: Tool name
            tool: Tool class or function
        """
        instance = cls()
        instance._tools[name] = tool
        logger.debug(f"Registered tool: {name}")

    @classmethod
    def get(cls, name: str) -> BaseTool | Callable | None:
        """Get tool instance.

        Args:
            name: Tool name

        Returns:
            Tool instance or None
        """
        instance = cls()
        tool = instance._tools.get(name)

        if tool is None:
            return None

        # Instantiate if class
        if isinstance(tool, type) and issubclass(tool, BaseTool):
            return tool()

        return tool

    @classmethod
    def get_all(cls) -> list[BaseTool | Callable]:
        """Get all tools."""
        instance = cls()
        tools = []
        for _, tool in instance._tools.items():
            if isinstance(tool, type) and issubclass(tool, BaseTool):
                tools.append(tool())
            else:
                tools.append(tool)
        return tools

    @classmethod
    def get_by_mode(cls, mode: str) -> list[BaseTool | Callable]:
        """Get tools by mode.

        Args:
            mode: Tool mode (sandbox/live)

        Returns:
            List of matching tools
        """
        instance = cls()
        tools = []
        for _, tool in instance._tools.items():
            if isinstance(tool, type) and issubclass(tool, BaseTool):
                tool_instance = tool()
                if getattr(tool_instance, "mode", "sandbox") == mode:
                    tools.append(tool_instance)
            else:
                # Function type tool, check attribute or default to sandbox
                tool_mode = getattr(tool, "mode", "sandbox")
                if tool_mode == mode:
                    tools.append(tool)
        return tools

    @classmethod
    def list_names(cls) -> list[str]:
        """List all tool names."""
        instance = cls()
        return list(instance._tools.keys())

    @classmethod
    def clear(cls):
        """Clear registry."""
        instance = cls()
        instance._tools.clear()

    @classmethod
    def load_default_tools(cls, mode: str = "sandbox"):
        """Load default tool set.

        Args:
            mode: Tool mode (sandbox/live)
        """
        if mode == "sandbox":
            cls._load_sandbox_tools()
        else:
            cls._load_live_tools()

    @classmethod
    def _load_sandbox_tools(cls):
        """Load sandbox tools."""
        try:
            from mobility_bench.tools.sandbox import (
                bicycling_route,
                bus_route,
                driving_route,
                query_poi,
                reverse_geocoding,
                search_around_poi,
                traffic_status,
                walking_route,
                weather_query,
            )

            cls.register("query_poi", query_poi)
            cls.register("driving_route", driving_route)
            cls.register("walking_route", walking_route)
            cls.register("bicycling_route", bicycling_route)
            cls.register("bus_route", bus_route)
            cls.register("weather_query", weather_query)
            cls.register("search_around_poi", search_around_poi)
            cls.register("reverse_geocoding", reverse_geocoding)
            cls.register("traffic_status", traffic_status)

            logger.info("Loaded sandbox tools from mobility_bench.tools.sandbox")

        except ImportError as e:
            logger.warning(f"Failed to load sandbox tools: {e}")
        except Exception as e:
            logger.error(f"Error loading sandbox tools: {e}")

    @classmethod
    def _load_live_tools(cls):
        """Load live tools."""
        # TODO: Implement live tool loading
        logger.warning("Live tool set not yet implemented")


def register_tool(name: str):
    """Tool registration decorator.

    Usage:
        @register_tool("my_tool")
        def my_tool(arg1, arg2):
            ...
    """

    def decorator(func_or_class):
        ToolRegistry.register(name, func_or_class)
        return func_or_class

    return decorator
