"""
Agent factory for creating agent instances.

This module provides the factory function for creating agents with
LLM binding, tool binding, and telemetry integration.
"""

import logging
from typing import Any

from langchain.agents import AgentState
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import AIMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph

from mobility_bench.agent.roles.base import AgentType
from mobility_bench.agent.roles.llm_manager import get_llm_for_agent
from mobility_bench.agent.utils.telemetry import log_event

logger = logging.getLogger(__name__)


class TelemetryCallbackHandler(BaseCallbackHandler):
    """Callback handler for telemetry integration."""

    run_inline = True  # Required by LangChain callback system

    def __init__(self, agent_name: str):
        super().__init__()
        self.agent_name = agent_name


def create_agent(
    agent_name: str,
    agent_type: AgentType | str,
    tools: list,
    system_prompt: str,
):
    """
    Create Agent instance (single call mode).

    Workflow:
    1. Get LLM
    2. Render system_prompt (pure role definition, no user info)
    3. Create tool mapping and bind tools
    4. Define agent_node (get history from state.messages + single LLM call + tool execution)
    5. Build StateGraph
    6. Add telemetry

    Args:
        agent_name: Agent name
        agent_type: Agent type
        tools: Available tools list
        system_prompt: System prompt string

    Returns:
        Compiled agent workflow
    """
    # 1. Get LLM and resolve type
    resolved_agent_type = (
        AgentType(agent_type) if isinstance(agent_type, str) else agent_type
    )
    llm = get_llm_for_agent(resolved_agent_type)

    logger.debug(
        f"[AGENT_CREATE] {agent_name} ({resolved_agent_type}) "
        f"with {len(tools)} tools"
    )

    # 2. Create system prompt message
    system_prompt_msg = SystemMessage(content=system_prompt)

    # 3. Create tool mapping and bind tools
    tool_map = {tool.name: tool for tool in tools}
    llm_with_tools = llm.bind_tools(tools) if tools else llm

    # 4. Define agent_node (single call logic)
    def agent_node(state: AgentState, config: RunnableConfig = None) -> dict:
        """Agent node: single call mode."""
        try:
            # Build message sequence: system prompt + history messages
            messages = [system_prompt_msg]
            messages.extend(state.get("messages", []))

            # Call LLM (single call only)
            response = llm_with_tools.invoke(messages, config)

            token_usage = None

            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                usage = response.usage_metadata
                # Get model name (optional)
                model_name = getattr(llm, 'model_name', str(llm))

                log_event(
                    event_type="llm_call",
                    payload={
                        "model": model_name,
                        "role": agent_name,
                        "prompt_tokens": usage.get("input_tokens", usage.get("prompt_tokens", 0)),
                        "completion_tokens": usage.get("output_tokens", usage.get("completion_tokens", 0)),
                        "total_tokens": usage.get("total_tokens", 0),
                    }
                )
                logger.info(
                    f"[{agent_name}] Token usage - "
                    f"Prompt: {usage.get('input_tokens', usage.get('prompt_tokens', 0))}, "
                    f"Completion: {usage.get('output_tokens', usage.get('completion_tokens', 0))}"
                )
                token_usage = {
                    "prompt_tokens": usage.get("input_tokens", usage.get("prompt_tokens", 0)),
                    "completion_tokens": usage.get("output_tokens", usage.get("completion_tokens", 0)),
                    "total_tokens": usage.get("total_tokens", 0),
                }

            # Check and execute tool calls
            if hasattr(response, "tool_calls") and response.tool_calls:
                logger.debug(
                    f"[{agent_name}] Detected {len(response.tool_calls)} tool calls"
                )

                result_messages = [response]

                for tool_call in response.tool_calls:
                    tool_name = tool_call.get("name", "")
                    tool_args = tool_call.get("args", {})
                    tool_id = tool_call.get("id", tool_name)

                    if tool_name in tool_map:
                        try:
                            tool_result = tool_map[tool_name].invoke(tool_args, config)
                            result_messages.append(
                                ToolMessage(
                                    content=str(tool_result),
                                    tool_call_id=tool_id,
                                    name=tool_name,
                                )
                            )
                            # Differentiate log display
                            if tool_name in {"handoff_to_reporter"}:
                                logger.debug(f"[{agent_name}] Flow control tool {tool_name} completed")
                            else:
                                logger.debug(f"[{agent_name}] Tool {tool_name} executed successfully")
                        except Exception as e:
                            error_msg = f"Tool {tool_name} execution failed: {str(e)}"
                            logger.error(
                                f"[{agent_name}] {error_msg}", exc_info=True
                            )
                            result_messages.append(
                                ToolMessage(
                                    content=error_msg,
                                    tool_call_id=tool_id,
                                    name=tool_name,
                                    status="error",
                                )
                            )
                    else:
                        error_msg = f"Unknown tool: {tool_name}"
                        logger.warning(f"[{agent_name}] {error_msg}")
                        result_messages.append(
                            ToolMessage(
                                content=error_msg,
                                tool_call_id=tool_id,
                                name=tool_name,
                                status="error",
                            )
                        )
                return {"messages": result_messages}

            # No tool calls, return response directly
            logger.debug(f"[{agent_name}] No tool calls, returning LLM response directly")
            return {"messages": [response]}

        except Exception as e:
            logger.error(f"[{agent_name}] Agent execution failed: {str(e)}", exc_info=True)
            error_message = AIMessage(content=f"Execution failed: {str(e)}")
            return {"messages": [error_message]}

    workflow = StateGraph(AgentState)
    workflow.add_node("agent", agent_node)
    workflow.set_entry_point("agent")
    workflow.set_finish_point("agent")

    # 6. Add telemetry
    telemetry_handler = TelemetryCallbackHandler(agent_name)
    return workflow.compile().with_config({"callbacks": [telemetry_handler]})
