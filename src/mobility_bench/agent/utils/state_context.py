"""
State context manager for tools to read/write runtime state without exposing
parameters to the LLM prompt. Uses ContextVar for isolation across threads/tasks.

Design principle: Tools can READ configuration and WRITE business data to State.
Uses atomic operations to avoid concurrency conflicts.
"""

import threading
from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import Any

_state_var: ContextVar[dict[str, Any] | None] = ContextVar(
    "state_context_var", default=None
)

# Global lock for atomic operations (used when needed)
_write_lock = threading.RLock()


class StateContext:
    """State accessor for reading configuration and writing business data."""

    @staticmethod
    def set_current_state(state: dict[str, Any] | None) -> None:
        _state_var.set(state)

    @staticmethod
    def get_current_state() -> dict[str, Any] | None:
        return _state_var.get()

    @staticmethod
    def get_field(field_name: str, default: Any = None) -> Any:
        """Read configuration parameter from State (e.g., default_city)."""
        current_state = StateContext.get_current_state()
        if current_state is None:
            return default
        return current_state.get(field_name, default)

    @staticmethod
    def get_current_plan():
        """
        Get current plan from State.

        Returns:
            Plan object or None
        """
        current_state = StateContext.get_current_state()
        if current_state is None:
            return None
        return current_state.get("current_plan")

    @staticmethod
    def set_current_plan(plan) -> bool:
        """
        Set current plan in State.

        Args:
            plan: Plan object

        Returns:
            bool: Whether setting was successful
        """
        current_state = StateContext.get_current_state()
        if current_state is None:
            return False

        try:
            with _write_lock:
                current_state["current_plan"] = plan
            return True
        except Exception:
            return False

    @staticmethod
    def update_poi_map(poi_name: str, poi_info: dict[str, Any]) -> bool:
        """
        Update poi_map in State.

        Args:
            poi_name: POI name
            poi_info: POI info dict, should contain coord, poiid etc.

        Returns:
            bool: Whether update was successful
        """
        current_state = StateContext.get_current_state()
        if current_state is None:
            return False

        try:
            with _write_lock:
                if "poi_map" not in current_state:
                    current_state["poi_map"] = {}
                current_state["poi_map"][poi_name] = poi_info
            return True
        except Exception:
            return False

    @staticmethod
    def get_poi_info(poi_name: str) -> dict[str, Any] | None:
        """
        Get POI info from poi_map.

        Args:
            poi_name: POI name

        Returns:
            POI info dict containing lat, lon, poiid etc.; None if not exists
        """
        poi_map = StateContext.get_field("poi_map", {})
        return poi_map.get(poi_name)


@contextmanager
def state_context(state: dict[str, Any]):
    """Bind a State dict to current context for tools during the context lifespan."""
    token: Token = _state_var.set(state)
    try:
        yield
    finally:
        # restore previous (important for nested calls, async tasks, or re-entrancy)
        _state_var.reset(token)
