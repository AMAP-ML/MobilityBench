"""
Prompt template management for agent system.

This module provides template loading and rendering for different agent roles
and frameworks.
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

# Initialize Jinja2 environment
_PROMPTS_DIR = Path(__file__).parent
_env = Environment(
    loader=FileSystemLoader(_PROMPTS_DIR),
    autoescape=select_autoescape(),
    trim_blocks=True,
    lstrip_blocks=True,
)


def get_prompt_template(framework: str, role: str) -> str:
    """
    Load and return a raw prompt template.

    Args:
        framework: Framework name (plan_and_execute, react)
        role: Role name (planner, worker, reporter, reasoning)

    Returns:
        Template string
    """
    template_path = f"{framework}/{role}.md"
    try:
        template = _env.get_template(template_path)
        return template.render()
    except Exception as e:
        raise ValueError(f"Error loading template {template_path}: {e}") from e


def get_system_prompt(
    framework: str,
    role: str,
    template_vars: dict[str, Any] | None = None,
) -> str:
    """
    Get rendered system prompt for use with create_agent.

    Args:
        framework: Framework name (plan_and_execute, react)
        role: Role name (planner, worker, reporter, reasoning)
        template_vars: Additional template variables

    Returns:
        Rendered system prompt string
    """
    # Base template variables
    vars_dict: dict[str, Any] = {
        "CURRENT_TIME": datetime.now().strftime("%a %b %d %Y %H:%M:%S %z"),
        "CURRENT_TIMESTAMP": int(datetime.now().timestamp()),
    }

    # Merge with provided variables
    if template_vars:
        vars_dict.update(template_vars)

    template_path = f"{framework}/{role}.md"
    try:
        template = _env.get_template(template_path)
        return template.render(**vars_dict)
    except Exception as e:
        raise ValueError(f"Error rendering template {template_path}: {e}") from e


class PromptLoader:
    """Prompt loader with caching support."""

    _cache: dict[str, str] = {}

    @classmethod
    def load(
        cls,
        framework: str,
        role: str,
        use_cache: bool = True,
        **kwargs: Any,
    ) -> str:
        """
        Load and render prompt template.

        Args:
            framework: Framework name
            role: Role name
            use_cache: Whether to use cached template
            **kwargs: Template variables

        Returns:
            Rendered prompt string
        """
        cache_key = f"{framework}/{role}"

        if use_cache and cache_key in cls._cache and not kwargs:
            return cls._cache[cache_key]

        prompt = get_system_prompt(framework, role, kwargs if kwargs else None)

        if use_cache and not kwargs:
            cls._cache[cache_key] = prompt

        return prompt

    @classmethod
    def clear_cache(cls) -> None:
        """Clear template cache."""
        cls._cache.clear()


# Convenience functions
def load_planner_prompt(framework: str = "plan_and_execute", **kwargs) -> str:
    """Load planner prompt."""
    return PromptLoader.load(framework, "planner", **kwargs)


def load_worker_prompt(framework: str = "plan_and_execute", **kwargs) -> str:
    """Load worker prompt."""
    return PromptLoader.load(framework, "worker", **kwargs)


def load_reporter_prompt(framework: str = "plan_and_execute", **kwargs) -> str:
    """Load reporter prompt."""
    return PromptLoader.load(framework, "reporter", **kwargs)


def load_reasoning_prompt(framework: str = "react", **kwargs) -> str:
    """Load reasoning prompt (for ReAct framework)."""
    return PromptLoader.load(framework, "reasoning", **kwargs)
