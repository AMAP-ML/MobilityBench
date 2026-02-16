"""
Plan-and-Execute framework nodes.

This module implements the core node functions for the Planner-Worker-Reporter architecture:
- planner_node: Generates and manages execution plans
- worker_node: Executes tool calls based on tasks
- reporter_node: Generates final reports
"""

import json
import logging
import re
from typing import Any, Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.messages.utils import AnyMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.utils.function_calling import convert_to_openai_tool
from langgraph.types import Command, Send

from mobility_bench.agent.graph.decorators import get_execution_recorder, record_execution
from mobility_bench.agent.graph.state import Plan, RawPlan, State, Status, Step, Task, Tool, raw_plan_to_plan
from mobility_bench.agent.prompts import get_system_prompt
from mobility_bench.agent.roles import AgentType, create_agent, get_llm_for_agent
from mobility_bench.agent.utils import log_event, state_context
from mobility_bench.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


def remove_json_codeblock(text: str) -> str:
    """Remove ```json ... ``` code blocks (including newlines)."""
    pattern = r'```json\s*(.*?)\s*```'
    match = re.search(pattern, text, re.DOTALL)

    if match:
        return match.group(1).strip()
    else:
        return text.strip()


@record_execution("planner", "planning")
async def planner_node(state: State, config: RunnableConfig):
    """Combined planner node: structured Plan system + route selection functionality."""
    recorder = get_execution_recorder(state, "planner")
    current_plan = state.get("current_plan")
    plan_iterations = state.get("plan_iterations", 0)

    # First entry: initialize messages, add background and user requirements
    if not current_plan and plan_iterations == 0:
        initial_messages = []

        context = state.get("context")
        if context:
            initial_messages.append(HumanMessage(content=f"Context information:\n{context}"))

        query = state.get("query")
        if query:
            initial_messages.append(HumanMessage(content=f"User requirement:\n{query}"))

        if initial_messages:
            updated_state = dict(state)
            updated_state["messages"] = list(state.get("messages", [])) + initial_messages
            state = updated_state

    # Loop detection: limit maximum iterations
    try:
        from mobility_bench.config.settings import Settings
        MAX_PLAN_ITERATIONS = Settings.get_instance().agent.plan_and_execute.max_plan_iterations
    except Exception:
        MAX_PLAN_ITERATIONS = 10
    if plan_iterations >= MAX_PLAN_ITERATIONS:
        logger.error(
            f"[PLANNER] Reached maximum iterations {MAX_PLAN_ITERATIONS}, terminating to avoid infinite loop"
        )
        recorder.tool_call("max_iterations_reached", {"iterations": plan_iterations})
        return Command(goto="reporter")

    logger.info(
        f"[PLANNER] Entering planner node - Plan status: {current_plan.status if current_plan else 'None'}, "
        f"Iteration: {plan_iterations}/{MAX_PLAN_ITERATIONS}"
    )

    # Format print current plan
    if current_plan:
        _print_plan_as_todo_list(current_plan)

    # Phase 1: Initial planning
    if not current_plan:
        logger.info("[PLANNER] Starting initial planning")
        return await _generate_initial_plan(state, recorder)

    # Phase 2: Execute current step
    elif _has_pending_step(current_plan):
        current_step = _get_current_step(current_plan)
        logger.info(
            f"[PLANNER] Current step: {current_plan.current_step_index}/{len(current_plan.steps)}"
        )

        # Execute worker tasks
        if _has_pending_worker_tasks(current_step):
            logger.info(
                f"[PLANNER] Executing step {current_plan.current_step_index} worker tasks"
            )
            return await _execute_worker_tasks(state, current_step, recorder)

        # Current step completed, analyze results and plan next
        else:
            logger.info(
                f"[PLANNER] Step {current_plan.current_step_index} completed"
            )
            return await _analyze_step_results_and_plan_next(
                state, current_step, recorder
            )

    # Phase 3: All steps completed, enter reporter
    else:
        logger.info("[PLANNER] All steps completed, entering reporter for final report")
        return Command(goto="reporter")


async def _generate_initial_plan(state: State, recorder):
    """Use LLM structured output to generate initial plan (RawPlan -> Plan)."""
    logger.info("[PLANNER] Starting to generate initial plan (structured output)")

    try:
        llm = get_llm_for_agent(AgentType.PLANNER)
        system_prompt = get_system_prompt("plan_and_execute", "planner")
        messages = [SystemMessage(content=system_prompt)]
        messages.extend(list[AnyMessage](state.get("messages", [])))

        poi_map = state.get("poi_map", {})
        if poi_map:
            poi_names = list(poi_map.keys())
            poi_list_str = ",".join(poi_names)
            messages.append(
                HumanMessage(content=f"Known location list: {poi_list_str}")
            )

        # Bind tool schema
        tool_schema = convert_to_openai_tool(RawPlan)
        llm_with_tool = llm.bind_tools([tool_schema], tool_choice="required")

        # Call LLM, get complete AIMessage response
        response: AIMessage = await llm_with_tool.ainvoke(messages)

        # Extract token usage
        planner_token = {}
        if hasattr(response, 'usage_metadata') and response.usage_metadata:
            usage = response.usage_metadata
            log_event(
                event_type="llm_call",
                payload={
                    "model": getattr(llm, 'model_name', str(llm)),
                    "role": "planner",
                    "prompt_tokens": usage.get("input_tokens", usage.get("prompt_tokens", 0)),
                    "completion_tokens": usage.get("output_tokens", usage.get("completion_tokens", 0)),
                    "total_tokens": usage.get("total_tokens", 0),
                }
            )
            planner_token = {
                "prompt_tokens": usage.get("input_tokens", usage.get("prompt_tokens", 0)),
                "completion_tokens": usage.get("output_tokens", usage.get("completion_tokens", 0)),
                "total_tokens": usage.get("total_tokens", 0),
            }
            logger.info(
                f"[PLANNER] Token usage - "
                f"Prompt: {usage.get('input_tokens', usage.get('prompt_tokens', 0))}, "
                f"Completion: {usage.get('output_tokens', usage.get('completion_tokens', 0))}"
            )

        # Parse response
        if response.tool_calls and len(response.tool_calls) > 0:
            tool_call = response.tool_calls[0]
            if tool_call["name"] != "RawPlan":
                raise ValueError(f"Unexpected tool call: {tool_call['name']}")
            tmp_args = tool_call["args"]
            if "_raw" in tmp_args:
                tmp_args = tmp_args["_raw"]
                if isinstance(tmp_args, str):
                    if not tmp_args.endswith("}"):
                        tmp_args += "}"
                    tmp_args = json.loads(tmp_args)
            raw_plan = RawPlan(**tmp_args)
        elif response.content:
            std_string = remove_json_codeblock(response.content)
            tool_info = json.loads(std_string)
            raw_plan = RawPlan(**tool_info)
        else:
            raise ValueError("No tool calls found in LLM response")

        if not raw_plan:
            raise ValueError("Failed to parse structured output from LLM response")

        plan = raw_plan_to_plan(raw_plan)

        # Collect training data
        system_content = system_prompt
        human_contents = []
        for msg in state.get("messages", []):
            if isinstance(msg, HumanMessage):
                human_contents.append(msg.content)

        planner_training_data = {
            "system": system_content,
            "human": "\n".join(human_contents),
            "steps": raw_plan.steps if raw_plan else [],
            "thinking": raw_plan.thinking,
            "intent": raw_plan.intent
        }

        if plan and plan.steps:
            logger.info(
                f"[PLANNER] Successfully generated plan (structured output), contains {len(plan.steps)} steps"
            )
            recorder.tool_call(
                "structured_plan_generated", {"steps_count": len(plan.steps)}
            )
            return Command(
                update={
                    "messages": state.get("messages", []),
                    "current_plan": plan,
                    "planner_thinking": raw_plan.thinking,
                    "planner_intent": raw_plan.intent,
                    "plan_iterations": state.get("plan_iterations", 0) + 1,
                    "planner_training_data": planner_training_data,
                    "planner_token_usage": planner_token
                },
                goto="planner",
            )

        logger.error("[PLANNER] Structured output did not generate valid plan (steps empty)")
        return Command(goto="reporter")

    except Exception as e:
        logger.error(f"[PLANNER] Structured output plan generation failed: {e}", exc_info=True)
        return Command(goto="reporter")


def _has_pending_step(plan: Plan) -> bool:
    """Check if there are pending steps."""
    if not plan or not plan.steps:
        return False
    return plan.current_step_index < len(plan.steps)


def _get_current_step(plan: Plan) -> Step | None:
    """Get current step."""
    if not plan or not plan.steps:
        return None
    if plan.current_step_index >= len(plan.steps):
        return None
    return plan.steps[plan.current_step_index]


def _has_pending_worker_tasks(step: Step) -> bool:
    """Check if step has pending worker tasks."""
    if not step or not step.tasks:
        return False
    return any(task.status == Status.PENDING for task in step.tasks)


async def _execute_worker_tasks(state: State, current_step: Step, recorder):
    """Execute worker tasks (parallel)."""
    pending_tasks = [
        t for t in current_step.tasks if t.status == Status.PENDING
    ]

    if not pending_tasks:
        return Command(goto="planner")

    # Record parallel tasks start
    recorder.parallel_start(len(pending_tasks), f"Executing {len(pending_tasks)} worker tasks")

    # Create parallel branches
    sends = []
    for task in pending_tasks:
        task.status = Status.EXECUTING
        task_state = dict(state)
        task_state.update({"current_task": task})
        sends.append(Send("worker_node", task_state))

    return Command(goto=sends)


async def _analyze_step_results_and_plan_next(
    state: State, current_step: Step, recorder
):
    """Analyze current step results, decide next step - supports dynamic plan adjustment."""
    # Check if all tasks in current step failed
    failed_tasks = [
        task for task in current_step.tasks if task.status == Status.FAILED
    ]

    # If all tasks failed, terminate execution
    if failed_tasks and len(failed_tasks) == len(current_step.tasks):
        current_plan = state["current_plan"]
        logger.error(
            f"[PLANNER] All tasks in step {current_plan.current_step_index} failed, terminating"
        )
        recorder.tool_call(
            "step_all_tasks_failed",
            {
                "step_index": current_plan.current_step_index,
                "failed_count": len(failed_tasks),
            },
        )
        return Command(goto="reporter")

    # Mark current step completed
    current_step.status = Status.COMPLETED
    current_plan = state["current_plan"]
    current_plan.current_step_index += 1

    # Record step completion
    recorder.tool_call(
        "step_completed",
        {"step_index": current_plan.current_step_index - 1},
    )

    # Based on analysis results: continue to next step or complete planning
    return Command(update={"current_plan": current_plan}, goto="planner")


def _print_plan_as_todo_list(plan: Plan):
    """Print plan as TODO list format (using logger.debug to reduce output)."""
    logger.debug("\n" + "=" * 60)
    logger.debug(f"Status: {plan.status}")
    logger.debug(f"Current step: {plan.current_step_index}")
    logger.debug("=" * 60)

    for i, step in enumerate(plan.steps):
        step_icon = (
            "DONE"
            if step.status == Status.COMPLETED
            else ("RUNNING" if step.status == Status.EXECUTING else "PENDING")
        )
        current_marker = " >> " if i == plan.current_step_index else "    "
        logger.debug(f"{current_marker}[{step_icon}] Step {i}")

        if step.tasks:
            logger.debug("      Tasks:")
            for j, task in enumerate(step.tasks):
                task_icon = (
                    "DONE"
                    if task.status == Status.COMPLETED
                    else ("RUNNING" if task.status == Status.EXECUTING else "PENDING")
                )
                logger.debug(f"        [{task_icon}] {j + 1}. {task.task_description}")

        logger.debug("")

    logger.debug("=" * 60 + "\n")


def _extract_task_result(result):
    """Extract task result from agent execution result, prioritizing actual tool return data."""
    result_messages = result.get("messages", [])

    if not result_messages:
        return "Task execution completed"

    # Prioritize ToolMessage, as tool's actual return data is there
    tool_results = []
    for msg in reversed(result_messages):
        if isinstance(msg, ToolMessage):
            if hasattr(msg, "content") and msg.content:
                content_str = str(msg.content)
                if len(content_str) > 5000:
                    logger.warning(
                        f"Tool {msg.name} returned oversized content: {len(content_str)} chars"
                    )
                tool_results.append(f"Tool {msg.name} returned: {content_str}")

    if tool_results:
        return "\n".join(tool_results)

    # If no tool results, find last AIMessage content
    for msg in reversed(result_messages):
        if isinstance(msg, AIMessage):
            if hasattr(msg, "content") and msg.content:
                content = str(msg.content).strip()
                if content and content not in ["Task completed", "Task execution completed", "Completed"]:
                    return content
            break

    return "Task execution completed"


def _extract_task_tools(result):
    """Extract tool call info from agent execution result."""
    result_messages = result.get("messages", [])
    ans = []
    if not result_messages:
        return ans

    for msg in reversed(result_messages):
        if isinstance(msg, AIMessage):
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tool_call in msg.tool_calls:
                    if isinstance(tool_call, str):
                        tool_call = tool_call.split("```json")[1].replace("```", "")
                        tool_call = json.loads(tool_call)

                    tmp = Tool(
                        tool_name=tool_call.get("name", ""),
                        tool_args=tool_call.get("args", {}),
                    )
                    ans.append(tmp)
                break

    if not ans:
        logger.warning("[WORKER] No tool calls found")

    return ans


def _extract_token_usage_from_messages(messages):
    """Safely extract token usage from last AIMessage in messages."""
    for msg in reversed(messages):
        if isinstance(msg, AIMessage):
            if hasattr(msg, 'usage_metadata') and msg.usage_metadata:
                usage = msg.usage_metadata
                input_tokens = usage.get("input_tokens", 0)
                output_tokens = usage.get("output_tokens", 0)
                total_tokens = usage.get("total_tokens", input_tokens + output_tokens)
                return {
                    "prompt_tokens": input_tokens,
                    "completion_tokens": output_tokens,
                    "total_tokens": total_tokens,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                }
    return None


@record_execution(
    lambda state: f"worker_{getattr(state.get('current_task'), 'task_id', 'unknown')}",
    "working",
)
async def worker_node(state: State, config: RunnableConfig):
    """Worker node: executes specific tool calls, handles worker tasks."""
    current_task = state.get("current_task")
    if not current_task:
        logger.warning("[WORKER] No current task, returning to planner")
        return Command(goto="planner")

    task_id = current_task.task_id
    recorder = get_execution_recorder(state, f"worker_{task_id}")

    logger.info(f"[WORKER] Starting worker task: {current_task.task_description}")

    # Add task description message
    task_message = AIMessage(content=f"Task_{task_id[-8:]}: {current_task.task_description}")

    # Get tools from registry
    tools = ToolRegistry.get_all()
    if not tools:
        logger.warning("[WORKER] No tools available, loading default tools")
        ToolRegistry.load_default_tools(mode="sandbox")
        tools = ToolRegistry.get_all()

    # Get system prompt
    system_prompt = get_system_prompt("plan_and_execute", "worker")

    agent = create_agent(
        "worker",
        AgentType.WORKER,
        tools,
        system_prompt,
    )

    try:
        # Execute agent with task message in state
        state_with_task = dict(state)
        state_with_task["messages"] = list(state.get("messages", [])) + [task_message]

        # Use state_context for tools to read State config
        with state_context(dict(state)):
            result = await agent.ainvoke(state_with_task)

        # Extract execution result
        execution_result = _extract_task_result(result)
        tool_list = _extract_task_tools(result)

        # Collect worker training data
        worker_training_data = None
        try:
            if result and "messages" in result:
                messages = result["messages"]
                human_contents = []
                tool_calls_list = []
                tool_results_map = {}
                ai_response = None

                for msg in messages:
                    if isinstance(msg, HumanMessage):
                        human_contents.append(msg.content)
                    elif isinstance(msg, ToolMessage):
                        tool_call_id = getattr(msg, "tool_call_id", "")
                        if tool_call_id:
                            tool_results_map[tool_call_id] = msg.content
                    elif isinstance(msg, AIMessage):
                        if hasattr(msg, "tool_calls") and msg.tool_calls:
                            for tool_call in msg.tool_calls:
                                tool_calls_list.append({
                                    "id": tool_call.get("id", ""),
                                    "name": tool_call.get("name", ""),
                                    "args": tool_call.get("args", {}),
                                })
                        if msg.content:
                            ai_response = msg.content

                tool_descriptions = []
                for tool in tools:
                    tool_descriptions.append({
                        "name": tool.name,
                        "description": tool.description if hasattr(tool, "description") else "",
                    })

                if system_prompt and human_contents and tool_calls_list:
                    worker_training_data = {
                        "task_id": task_id,
                        "system": system_prompt,
                        "tools": tool_descriptions,
                        "human": "\n".join(human_contents),
                        "tool_calls": tool_calls_list,
                        "tool_results": tool_results_map,
                        "ai_response": ai_response or execution_result,
                    }
        except Exception as e:
            logger.error(f"[WORKER] Task {task_id} training data collection failed: {e}", exc_info=True)

        # Check for forbidden flow control tools
        forbidden_tools = ["handoff_to_planner", "handoff_to_reporter"]
        used_forbidden_tools = [
            tool.tool_name
            for tool in tool_list
            if hasattr(tool, "tool_name") and tool.tool_name in forbidden_tools
        ]
        if used_forbidden_tools:
            logger.error(
                f"[WORKER] Task {task_id} used forbidden flow control tools: {used_forbidden_tools}"
            )
            current_task.execution_result = f"Task failed: Worker should not use flow control tools ({', '.join(used_forbidden_tools)})"
            current_task.tool_list = tool_list
            current_task.status = Status.FAILED
            recorder.tool_call(
                "worker_forbidden_tool",
                {"task_id": task_id, "forbidden_tools": used_forbidden_tools},
            )
            return Command(goto="planner")

        # Check if any tools were called
        if not tool_list:
            logger.error(f"[WORKER] Task {task_id} did not call any tools, marking as failed")
            current_task.execution_result = f"Task failed: No tools called. Task description: {current_task.task_description}"
            current_task.tool_list = []
            current_task.status = Status.FAILED
            recorder.tool_call(
                "worker_no_tools",
                {
                    "task_id": task_id,
                    "task_description": current_task.task_description,
                    "execution_result": execution_result,
                },
            )
            return Command(
                update={"messages": [task_message]},
                goto="planner"
            )

        current_task.status = Status.COMPLETED
        logger.info(
            f"[WORKER] Task completed: {task_id}, called {len(tool_list)} tools"
        )
        recorder.tool_call(
            "worker_completed", {"task_id": task_id, "tools_count": len(tool_list)}
        )

        # Update State with worker training data
        update_state = {}
        if worker_training_data:
            update_state["worker_training_data"] = [worker_training_data]
        update_state["messages"] = result.get("messages", [])

        worker_token_usage = _extract_token_usage_from_messages(result.get("messages", []))
        if worker_token_usage:
            update_state["worker_token_usage"] = worker_token_usage

        return Command(
            update=update_state,
            goto="planner"
        )

    except Exception as e:
        logger.error(f"[WORKER] Task execution exception: {e}", exc_info=True)
        current_task.execution_result = f"Worker task failed: {str(e)}"
        current_task.status = Status.FAILED
        recorder.tool_call("worker_exception", {"task_id": task_id, "error": str(e)})

        return Command(
            update={"messages": [task_message, AIMessage(content=f"Task execution exception: {str(e)}")]},
            goto="planner"
        )


@record_execution("reporter", "reporting")
async def reporter_node(state: State, config: RunnableConfig):
    """Reporter: generates final markdown report.

    Core functions:
    1. Generate report based on tool call history in state.messages
    2. Ensure reporter generates report based on actual tool return data, not fabricated
    3. Generate markdown format final report
    """
    # Add report requirement message
    reporter_messages = [
        HumanMessage(content="Summary task: Please generate a detailed Markdown format report based on the above requirements and execution results.")
    ]

    # Get system prompt
    system_prompt = get_system_prompt("plan_and_execute", "reporter")

    # Create reporter agent and generate final report
    tools: list = []
    agent = create_agent(
        "reporter",
        AgentType.REPORTER,
        tools,
        system_prompt,
    )

    # Execute agent with report requirement in state
    state_with_request = dict(state)
    state_with_request["messages"] = list(state.get("messages", [])) + reporter_messages

    # Reporter generates final report based on complete message history
    result = await agent.ainvoke(state_with_request)
    updated_messages = result.get("messages", [])
    reporter_token_usage = _extract_token_usage_from_messages(updated_messages)

    # Extract markdown report (from last AI message)
    plan_result_markdown = None
    for msg in reversed(updated_messages):
        if hasattr(msg, "type") and msg.type == "ai":
            if hasattr(msg, "content") and msg.content:
                if isinstance(msg.content, str) and msg.content.strip():
                    plan_result_markdown = msg.content.strip()
                    break
        elif isinstance(msg, AIMessage) and msg.content:
            if isinstance(msg.content, str) and msg.content.strip():
                plan_result_markdown = msg.content.strip()
                break

    if plan_result_markdown:
        logger.info(
            f"[REPORTER] Successfully generated markdown report, length: {len(plan_result_markdown)}"
        )
    else:
        logger.warning("[REPORTER] Failed to extract valid markdown report")
        plan_result_markdown = "Sorry, failed to generate a valid report."

    # Collect reporter training data
    reporter_training_data = None
    try:
        human_contents = []
        for msg in state.get("messages", []):
            if isinstance(msg, HumanMessage):
                human_contents.append(msg.content)

        context = state.get("context")
        if context:
            human_contents.append(f"Context information: {context}")

        human_input = "\n".join(human_contents) if human_contents else "No context"
        final_answer = plan_result_markdown

        if system_prompt and human_input and final_answer:
            reporter_training_data = {
                "system": system_prompt,
                "human": human_input,
                "final_answer": final_answer
            }
    except Exception as e:
        logger.error(f"[REPORTER] Training data construction failed: {e}", exc_info=True)

    return Command(
        update={
            "messages": reporter_messages + updated_messages,
            "plan_result": plan_result_markdown,
            "reporter_training_data": reporter_training_data,
            "reporter_token_usage": reporter_token_usage,
        },
        goto="__end__",
    )
