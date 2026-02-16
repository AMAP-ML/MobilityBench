"""
ReAct framework nodes.

This module implements the core node functions for the Reasoning-Action-Observation loop:
- reasoning_node: Generates thoughts and decides next action
- action_node: Executes tools or finishes
- should_continue: Routes to continue or end
"""

import json
import logging
import re
from typing import Any, Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command

from mobility_bench.agent.graph.decorators import get_execution_recorder, record_execution
from mobility_bench.agent.graph.state import State
from mobility_bench.agent.prompts import get_system_prompt
from mobility_bench.agent.roles import AgentType, get_llm_for_agent
from mobility_bench.agent.utils import log_event, state_context
from mobility_bench.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

# Maximum iterations for ReAct loop
MAX_REACT_ITERATIONS = 15


def _parse_react_response(content: str) -> dict[str, Any]:
    """Parse ReAct JSON response from LLM output."""
    # Try to extract JSON from content
    content = content.strip()

    # Try to find JSON block
    json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
    if json_match:
        content = json_match.group(1)
    else:
        # Try to find raw JSON object
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            content = json_match.group(0)

    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        logger.warning(f"[REACT] Failed to parse JSON response: {e}")
        # Return a default finish action if parsing fails
        return {
            "thought": "Unable to parse response, ending with available information.",
            "action": "finish",
            "final_answer": content
        }


def _build_tool_descriptions() -> str:
    """Build tool descriptions for the prompt."""
    tools = ToolRegistry.get_all()
    if not tools:
        return "No tools available."

    descriptions = []
    for tool in tools:
        desc = f"- {tool.name}"
        if hasattr(tool, 'description') and tool.description:
            desc += f": {tool.description[:100]}"
        descriptions.append(desc)

    return "\n".join(descriptions)


@record_execution("react_reasoning", "reasoning")
async def reasoning_node(state: State, config: RunnableConfig) -> Command:
    """
    Reasoning node: Analyzes situation and decides next action.

    This node:
    1. Gets current context from messages
    2. Uses LLM to generate thought and decide action
    3. Updates state with thought and action decision
    """
    recorder = get_execution_recorder(state, "react_reasoning")
    iterations = state.get("react_iterations", 0)

    # Check iteration limit
    if iterations >= MAX_REACT_ITERATIONS:
        logger.warning(f"[REACT] Reached max iterations ({MAX_REACT_ITERATIONS}), forcing finish")
        return Command(
            update={
                "react_finish": True,
                "plan_result": "Reached maximum iterations. Please try with a simpler query.",
            },
            goto="action"
        )

    logger.info(f"[REACT] Reasoning iteration {iterations + 1}/{MAX_REACT_ITERATIONS}")

    try:
        llm = get_llm_for_agent(AgentType.PLANNER)  # Use reasoning model
        system_prompt = get_system_prompt("react", "reasoning")

        # Build messages
        messages = [SystemMessage(content=system_prompt)]

        # Add context and query on first iteration
        if iterations == 0:
            context = state.get("context")
            if context:
                messages.append(HumanMessage(content=f"Context: {context}"))

            query = state.get("query")
            if query:
                messages.append(HumanMessage(content=f"User query: {query}"))

            # Add available tools info
            tools_info = _build_tool_descriptions()
            messages.append(HumanMessage(content=f"Available tools:\n{tools_info}"))

        # Add conversation history
        messages.extend(state.get("messages", []))

        # Call LLM
        response = await llm.ainvoke(messages)

        # Extract token usage
        token_usage = {}
        if hasattr(response, 'usage_metadata') and response.usage_metadata:
            usage = response.usage_metadata
            token_usage = {
                "prompt_tokens": usage.get("input_tokens", usage.get("prompt_tokens", 0)),
                "completion_tokens": usage.get("output_tokens", usage.get("completion_tokens", 0)),
                "total_tokens": usage.get("total_tokens", 0),
            }
            log_event(
                event_type="llm_call",
                payload={
                    "model": getattr(llm, 'model_name', str(llm)),
                    "role": "react_reasoning",
                    **token_usage
                }
            )

        # Parse response
        parsed = _parse_react_response(response.content)

        thought = parsed.get("thought", "")
        action = parsed.get("action", "finish")
        tool_name = parsed.get("tool_name", "")
        tool_args = parsed.get("tool_args", {})
        final_answer = parsed.get("final_answer", "")

        logger.info(f"[REACT] Thought: {thought[:100]}...")
        logger.info(f"[REACT] Action: {action}")

        # Update state
        thoughts = list(state.get("react_thoughts", []))
        thoughts.append(thought)

        actions = list(state.get("react_actions", []))
        actions.append({
            "action": action,
            "tool_name": tool_name,
            "tool_args": tool_args,
        })

        # Add AI message to history
        new_messages = list(state.get("messages", []))
        new_messages.append(AIMessage(content=f"Thought: {thought}\nAction: {action}"))

        update_dict = {
            "messages": new_messages,
            "react_iterations": iterations + 1,
            "react_thoughts": thoughts,
            "react_actions": actions,
            "react_current_action": action,
            "react_current_tool_name": tool_name,
            "react_current_tool_args": tool_args,
            "token_usage": token_usage,
        }

        if action == "finish":
            update_dict["react_finish"] = True
            update_dict["plan_result"] = final_answer

        recorder.tool_call("reasoning_complete", {"action": action, "iteration": iterations + 1})

        return Command(update=update_dict, goto="action")

    except Exception as e:
        logger.error(f"[REACT] Reasoning error: {e}", exc_info=True)
        return Command(
            update={
                "react_finish": True,
                "plan_result": f"Error during reasoning: {str(e)}",
            },
            goto="action"
        )


@record_execution("react_action", "acting")
async def action_node(state: State, config: RunnableConfig) -> Command:
    """
    Action node: Executes tool or prepares to finish.

    This node:
    1. Checks if action is 'finish' - if so, just pass through
    2. If action is 'call_tool', executes the tool
    3. Adds observation (tool result) to messages
    """
    recorder = get_execution_recorder(state, "react_action")

    action = state.get("react_current_action", "finish")
    tool_name = state.get("react_current_tool_name", "")
    tool_args = state.get("react_current_tool_args", {})

    logger.info(f"[REACT] Action node - action: {action}, tool: {tool_name}")

    # If finish action, nothing to do
    if action == "finish" or state.get("react_finish"):
        recorder.tool_call("action_finish", {})
        return Command(update={}, goto="__end__")

    # Execute tool
    if action == "call_tool" and tool_name:
        try:
            # Get tool from registry
            tools = ToolRegistry.get_all()
            if not tools:
                ToolRegistry.load_default_tools(mode="sandbox")
                tools = ToolRegistry.get_all()

            tool_map = {t.name: t for t in tools}

            if tool_name not in tool_map:
                error_msg = f"Unknown tool: {tool_name}"
                logger.warning(f"[REACT] {error_msg}")
                observation = f"Error: {error_msg}"
            else:
                # Execute tool
                tool = tool_map[tool_name]
                logger.info(f"[REACT] Calling tool: {tool_name} with args: {tool_args}")

                with state_context(dict(state)):
                    result = tool.invoke(tool_args, config)

                observation = str(result)
                logger.info(f"[REACT] Tool result: {observation[:200]}...")

            # Add observation to messages
            new_messages = list(state.get("messages", []))
            new_messages.append(HumanMessage(content=f"Observation: {observation}"))

            recorder.tool_call("tool_executed", {"tool_name": tool_name})

            return Command(
                update={"messages": new_messages},
                goto="reasoning"
            )

        except Exception as e:
            logger.error(f"[REACT] Tool execution error: {e}", exc_info=True)
            error_observation = f"Tool execution error: {str(e)}"

            new_messages = list(state.get("messages", []))
            new_messages.append(HumanMessage(content=f"Observation: {error_observation}"))

            return Command(
                update={"messages": new_messages},
                goto="reasoning"
            )

    # Default: continue to reasoning
    return Command(update={}, goto="reasoning")


def should_continue(state: State) -> Literal["continue", "end"]:
    """
    Routing function: decides whether to continue loop or end.

    Returns:
        "continue" to go back to reasoning
        "end" to finish execution
    """
    if state.get("react_finish"):
        return "end"

    iterations = state.get("react_iterations", 0)
    if iterations >= MAX_REACT_ITERATIONS:
        return "end"

    action = state.get("react_current_action", "")
    if action == "finish":
        return "end"

    return "continue"
