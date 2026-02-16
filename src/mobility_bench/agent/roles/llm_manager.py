"""
LLM management for agent system.

This module provides LLM configuration and instantiation for different agent roles.
"""

from enum import Enum
from typing import Any

from langchain_openai import ChatOpenAI

from mobility_bench.agent.roles.base import AgentType
from mobility_bench.config.settings import ModelConfig, Settings


class LLMType(str, Enum):
    """LLM type enumeration."""

    BASIC = "basic"
    REASONING = "reasoning"
    REPORTER = "reporter"


# Agent-LLM mapping configuration
#
# Model assignment principles (best practices):
# - REASONING_MODEL: For critical decisions, complex reasoning, comprehensive understanding
#   * PLANNER: Complex task decomposition, plan creation, dynamic adjustment, requirement understanding
#   * REPORTER: Comprehensive understanding of multiple task results, generating natural language reports
#
# - BASIC_MODEL: For simple tool calls, information collection
#   * WORKER: Tool calls, mainly parameter passing, no complex reasoning needed
#
AGENT_LLM_MAP: dict[AgentType, LLMType] = {
    AgentType.PLANNER: LLMType.REASONING,  # Complex planning and requirement understanding
    AgentType.WORKER: LLMType.BASIC,  # Tool calls, use BASIC (lower cost and latency)
    AgentType.REPORTER: LLMType.REPORTER,  # Comprehensive understanding, use dedicated REPORTER model
}


class LLMManager:
    """LLM Manager for managing LLM instances across agent roles."""

    def __init__(self, settings: Settings | None = None, model_config: ModelConfig | None = None):
        """
        Initialize LLM Manager.

        Args:
            settings: Global settings object
            model_config: Specific model configuration to use
        """
        self.settings = settings or Settings.get_instance()
        self.model_config = model_config
        self._llm_cache: dict[str, ChatOpenAI] = {}

    def set_model_config(self, model_config: ModelConfig) -> None:
        """Set model configuration and clear cache."""
        self.model_config = model_config
        self._llm_cache.clear()

    def get_llm(self, llm_type: LLMType = LLMType.BASIC) -> ChatOpenAI:
        """
        Get LLM instance by type.

        Args:
            llm_type: LLM type (BASIC, REASONING, REPORTER)

        Returns:
            ChatOpenAI instance
        """
        cache_key = f"{llm_type.value}"
        if cache_key in self._llm_cache:
            return self._llm_cache[cache_key]

        model_name = self._get_model_name(llm_type)
        llm = self._create_llm(model_name)
        self._llm_cache[cache_key] = llm
        return llm

    def get_llm_for_agent(self, agent_type: AgentType) -> ChatOpenAI:
        """
        Get LLM instance for specific agent type.

        Args:
            agent_type: Agent type (PLANNER, WORKER, REPORTER)

        Returns:
            ChatOpenAI instance
        """
        llm_type = self._get_llm_type_for_agent(agent_type)
        return self.get_llm(llm_type)

    def _get_llm_type_for_agent(self, agent_type: AgentType) -> LLMType:
        """Get LLM type for agent type."""
        llm_type = AGENT_LLM_MAP.get(agent_type)
        if llm_type is None:
            raise ValueError(f"No LLM type configured for agent: {agent_type}")
        return llm_type

    def _get_model_name(self, llm_type: LLMType) -> str:
        """Get model name for LLM type."""
        if self.model_config and self.model_config.roles:
            # Try to get from model config roles
            role_map = {
                LLMType.BASIC: "worker",
                LLMType.REASONING: "planner",
                LLMType.REPORTER: "reporter",
            }
            role_name = role_map.get(llm_type, "worker")
            model_name = self.model_config.roles.get(role_name)
            if model_name:
                return model_name

        # Fallback to model config name
        if self.model_config:
            return self.model_config.name

        raise ValueError(f"No model name configured for LLM type: {llm_type}")

    def _create_llm(self, model_name: str) -> ChatOpenAI:
        """Create ChatOpenAI instance."""
        if not self.model_config:
            raise ValueError("Model config not set")

        extra_body: dict[str, Any] = {}

        # Validate and normalize base_url
        base_url = self.model_config.base_url
        if base_url and not base_url.startswith(("http://", "https://")):
            # Add https:// by default if protocol is missing
            base_url = f"https://{base_url}"

        llm = ChatOpenAI(
            base_url=base_url,
            api_key=self.model_config.api_key,
            model=model_name,
            temperature=self.model_config.temperature,
            max_tokens=self.model_config.max_tokens,
            timeout=self.model_config.timeout,
            extra_body=extra_body if extra_body else None,
        )

        return llm


# Global LLM manager instance
_llm_manager: LLMManager | None = None


def get_llm_manager(settings: Settings | None = None, model_config: ModelConfig | None = None) -> LLMManager:
    """Get or create global LLM manager instance."""
    global _llm_manager
    if _llm_manager is None:
        _llm_manager = LLMManager(settings, model_config)
    elif model_config and model_config != _llm_manager.model_config:
        _llm_manager.set_model_config(model_config)
    return _llm_manager


def get_llm(llm_type: LLMType = LLMType.BASIC) -> ChatOpenAI:
    """Get LLM instance by type (convenience function)."""
    return get_llm_manager().get_llm(llm_type)


def get_llm_for_agent(agent_type: AgentType) -> ChatOpenAI:
    """Get LLM instance for agent type (convenience function)."""
    return get_llm_manager().get_llm_for_agent(agent_type)


def set_model_config(model_config: ModelConfig) -> None:
    """Set model configuration for LLM manager."""
    get_llm_manager().set_model_config(model_config)
