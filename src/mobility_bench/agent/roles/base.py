"""
Agent type definitions.

This module defines the different types of agents used in the
Planner-Worker-Reporter architecture.
"""

from enum import Enum


class AgentType(str, Enum):
    """Agent type enumeration."""

    # Planning role - decomposes tasks and creates execution plans
    PLANNER = "planner"

    # Execution role - executes tools and collects information
    WORKER = "worker"

    # Output role - generates final reports
    REPORTER = "reporter"
