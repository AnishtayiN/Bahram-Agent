"""
Planner.

Public objects: ``LLMProviderForPlanner``, ``Planner``.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any, Protocol

from bahram.autonomy.plan import Plan, PlanStatus, PlanStep, StepStatus

logger = logging.getLogger(__name__)


class LLMProviderForPlanner(Protocol):
    """
    LLM provider for planner.
    """

    async def complete(
        self, messages: list[Any], tools: list[dict[str, Any]] | None = None, **kwargs: Any
    ) -> Any:
        """Send a chat completion request and return the raw provider response.

        Args:
            messages (list[Any]): conversation history to send.
            tools (list[dict[str, Any]] | None): OpenAI-style tool schemas.
                Defaults to ``None``.
            **kwargs (Any): provider specific overrides.

        Returns:
            Any: the provider response object (``AgentResponse`` for the real
                engine implementations).

        Note:
            Coroutine - must be awaited.
        """
        ...


PLANNING_SYSTEM_PROMPT = """You are a planning engine. Given a goal, create a structured \
execution plan.

Analyze the goal and produce a JSON plan with these fields:
- strategy: high-level approach
- rationale: why this approach
- success_criteria: list of criteria that indicate success
- risk_assessment: potential risks
- steps: array of step objects, each with:
  - id: unique step identifier (e.g. "step_1")
  - objective: what this step achieves
  - dependencies: list of step IDs this depends on
  - required_tools: tools needed (e.g. ["bash", "read", "write"])
  - required_capabilities: capabilities needed (e.g. ["filesystem.read", "shell.execute"])
  - verification_criteria: list of verification checks, each with:
    - type: "command" | "file_exists" | "content_check" | "test_execution"
    - params: type-specific parameters

Rules:
- Only create steps that are actually necessary
- Minimize dependencies — prefer parallel execution when possible
- Be specific about verification criteria
- If the goal is trivial, create only 1-2 steps
- If complex, break into 3-8 steps maximum
- Each step should be independently verifiable

Output ONLY valid JSON, no markdown."""

PLANNING_USER_TEMPLATE = """Goal: {goal}

Context:
{context}

Available tools: {tools}

Create a structured plan."""

REPLAN_SYSTEM_PROMPT = """You are a replanning engine. A plan step has failed. Analyze the \
failure and produce a revised plan.

The original plan and the failed step are provided. Produce a JSON response with:
- diagnosis: what went wrong
- repair_strategy: how to fix it
- revised_steps: array of steps to replace/insert after the failed step
- keep_completed: whether to keep completed steps (true/false)

Rules:
- Preserve completed work whenever possible
- Create minimal repair steps
- Consider alternative approaches
- If the original approach is fundamentally flawed, suggest a different strategy

Output ONLY valid JSON, no markdown."""


class Planner:
    """
    Planner.
    """

    def __init__(self, provider: LLMProviderForPlanner | None = None) -> None:
        """
        Initialise a Planner instance.

        Args:
            provider (LLMProviderForPlanner | None): provider. Defaults to ``None``.
        """
        self._provider = provider
        self._plans: dict[str, Plan] = {}

    def set_provider(self, provider: LLMProviderForPlanner) -> None:
        """
        Set the provider.

        Args:
            provider (LLMProviderForPlanner): provider.
        """
        self._provider = provider

    async def create_plan(
        self,
        goal: str,
        run_id: str = "",
        context: str = "",
        available_tools: list[str] | None = None,
        memory_context: str = "",
        skill_context: str = "",
    ) -> Plan:
        """
        Create plan.

        Args:
            goal (str): goal string.
            run_id (str): run identifier. Defaults to ``''``.
            context (str): context string. Defaults to ``''``.
            available_tools (list[str] | None): collection of available tools. Defaults to ``None``.
            memory_context (str): memory context string. Defaults to ``''``.
            skill_context (str): skill context string. Defaults to ``''``.

        Returns:
            Plan: the resulting Plan.

        Note:
            Coroutine - must be awaited.
        """
        plan_id = f"plan_{uuid.uuid4().hex[:8]}"
        run_id = run_id or f"run_{uuid.uuid4().hex[:8]}"

        plan = Plan(
            id=plan_id,
            run_id=run_id,
            goal=goal,
            status=PlanStatus.PLANNING,
        )

        if self._provider is None:
            plan = self._create_fallback_plan(plan)
            plan.status = PlanStatus.READY
            plan.updated_at = time.time()
            self._plans[plan_id] = plan
            return plan

        context_parts = []
        if memory_context:
            context_parts.append(f"Relevant memories:\n{memory_context}")
        if skill_context:
            context_parts.append(f"Relevant skills:\n{skill_context}")
        if context:
            context_parts.append(f"Additional context:\n{context}")
        context_str = "\n\n".join(context_parts) if context_parts else "No additional context."

        tools_str = ", ".join(available_tools) if available_tools else "No tools specified."

        user_msg = PLANNING_USER_TEMPLATE.format(goal=goal, context=context_str, tools=tools_str)

        try:
            from bahram.core.engine import Message, MessageRole

            messages = [
                Message(role=MessageRole.SYSTEM, content=PLANNING_SYSTEM_PROMPT),
                Message(role=MessageRole.USER, content=user_msg),
            ]

            response = await self._provider.complete(messages, tools=None)
            plan_data = self._parse_plan_response(response.content)
            plan = self._build_plan_from_llm(plan, plan_data)
        except Exception as e:
            logger.warning(f"LLM planning failed, using fallback: {e}")
            plan = self._create_fallback_plan(plan)

        plan.status = PlanStatus.READY
        plan.updated_at = time.time()
        self._plans[plan_id] = plan
        return plan

    async def replan(
        self,
        plan: Plan,
        failed_step: PlanStep,
        error: str,
        context: str = "",
    ) -> Plan:
        """
        Replan.

        Args:
            plan (Plan): plan.
            failed_step (PlanStep): failed step.
            error (str): error string.
            context (str): context string. Defaults to ``''``.

        Returns:
            Plan: the resulting Plan.

        Note:
            Coroutine - must be awaited.
        """
        if self._provider is None:
            plan = self._replan_fallback(plan, failed_step, error)
            plan.replan_count += 1
            plan.updated_at = time.time()
            return plan

        from bahram.core.engine import Message, MessageRole

        plan_context = json.dumps(plan.to_dict(), indent=2, default=str)
        failed_context = json.dumps(failed_step.to_dict(), indent=2, default=str)

        user_msg = f"""Original plan:
{plan_context}

Failed step:
{failed_context}

Error: {error}

Additional context: {context or "None"}

Produce a revised plan."""

        try:
            messages = [
                Message(role=MessageRole.SYSTEM, content=REPLAN_SYSTEM_PROMPT),
                Message(role=MessageRole.USER, content=user_msg),
            ]

            response = await self._provider.complete(messages, tools=None)
            replan_data = self._parse_plan_response(response.content)
            plan = self._apply_replan(plan, failed_step, replan_data)
        except Exception as e:
            logger.warning(f"LLM replanning failed, using fallback: {e}")
            plan = self._replan_fallback(plan, failed_step, error)

        plan.replan_count += 1
        plan.updated_at = time.time()
        return plan

    def get_plan(self, plan_id: str) -> Plan | None:
        """
        Return the plan.

        Args:
            plan_id (str): plan identifier.

        Returns:
            Plan | None: the resulting object, or ``None`` when it is not available.
        """
        return self._plans.get(plan_id)

    def get_plan_by_run(self, run_id: str) -> Plan | None:
        """
        Return the plan by run.

        Args:
            run_id (str): run identifier.

        Returns:
            Plan | None: the resulting object, or ``None`` when it is not available.
        """
        for plan in self._plans.values():
            if plan.run_id == run_id:
                return plan
        return None

    def list_plans(self) -> list[Plan]:
        """
        List plans.

        Returns:
            list[Plan]: a sequence of Plan entries (empty when there is nothing to report).
        """
        return list(self._plans.values())

    def _parse_plan_response(self, content: str) -> dict[str, Any]:
        content = content.strip()
        if content.startswith("```"):
            lines = content.split("\n")
            lines = [line for line in lines if not line.strip().startswith("```")]
            content = "\n".join(lines)

        try:
            return json.loads(content)
        except json.JSONDecodeError:
            start = content.find("{")
            end = content.rfind("}") + 1
            if start >= 0 and end > start:
                try:
                    return json.loads(content[start:end])
                except json.JSONDecodeError:
                    pass
            return {}

    def _build_plan_from_llm(self, plan: Plan, data: dict[str, Any]) -> Plan:
        plan.strategy = data.get("strategy", "")
        plan.rationale = data.get("rationale", "")
        plan.success_criteria = data.get("success_criteria", [])
        plan.risk_assessment = data.get("risk_assessment", "")

        for step_data in data.get("steps", []):
            step = PlanStep(
                id=step_data.get("id", f"step_{len(plan.steps) + 1}"),
                plan_id=plan.id,
                objective=step_data.get("objective", ""),
                dependencies=step_data.get("dependencies", []),
                required_tools=step_data.get("required_tools", []),
                required_capabilities=step_data.get("required_capabilities", []),
                verification_criteria=step_data.get("verification_criteria", []),
            )
            plan.steps.append(step)

        return plan

    def _create_fallback_plan(self, plan: Plan) -> Plan:
        goal_lower = plan.goal.lower()

        if any(w in goal_lower for w in ("fix", "debug", "repair", "error")):
            steps = [
                PlanStep(
                    id="step_1",
                    plan_id=plan.id,
                    objective="Investigate the issue",
                    required_tools=["read", "bash"],
                ),
                PlanStep(
                    id="step_2",
                    plan_id=plan.id,
                    objective="Identify root cause",
                    dependencies=["step_1"],
                    required_tools=["read"],
                ),
                PlanStep(
                    id="step_3",
                    plan_id=plan.id,
                    objective="Implement fix",
                    dependencies=["step_2"],
                    required_tools=["write", "edit"],
                ),
                PlanStep(
                    id="step_4",
                    plan_id=plan.id,
                    objective="Verify fix works",
                    dependencies=["step_3"],
                    required_tools=["bash"],
                    verification_criteria=[{"type": "test_execution", "params": {}}],
                ),
            ]
        elif any(w in goal_lower for w in ("create", "build", "implement", "add")):
            steps = [
                PlanStep(
                    id="step_1",
                    plan_id=plan.id,
                    objective="Analyze requirements and existing code",
                    required_tools=["read"],
                ),
                PlanStep(
                    id="step_2",
                    plan_id=plan.id,
                    objective="Implement the solution",
                    dependencies=["step_1"],
                    required_tools=["write", "edit"],
                ),
                PlanStep(
                    id="step_3",
                    plan_id=plan.id,
                    objective="Verify implementation",
                    dependencies=["step_2"],
                    required_tools=["bash"],
                    verification_criteria=[{"type": "test_execution", "params": {}}],
                ),
            ]
        elif any(w in goal_lower for w in ("research", "investigate", "analyze", "understand")):
            steps = [
                PlanStep(
                    id="step_1",
                    plan_id=plan.id,
                    objective="Gather relevant information",
                    required_tools=["read", "websearch"],
                ),
                PlanStep(
                    id="step_2",
                    plan_id=plan.id,
                    objective="Analyze findings",
                    dependencies=["step_1"],
                    required_tools=["read"],
                ),
                PlanStep(
                    id="step_3",
                    plan_id=plan.id,
                    objective="Synthesize results",
                    dependencies=["step_2"],
                    required_tools=[],
                ),
            ]
        else:
            steps = [
                PlanStep(
                    id="step_1",
                    plan_id=plan.id,
                    objective="Analyze the goal and context",
                    required_tools=["read"],
                ),
                PlanStep(
                    id="step_2",
                    plan_id=plan.id,
                    objective="Execute necessary actions",
                    dependencies=["step_1"],
                    required_tools=["bash", "read", "write"],
                ),
                PlanStep(
                    id="step_3",
                    plan_id=plan.id,
                    objective="Verify results",
                    dependencies=["step_2"],
                    required_tools=["bash"],
                ),
            ]

        plan.steps = steps
        plan.strategy = "Structured analysis and execution"
        plan.rationale = "Fallback plan based on goal pattern analysis"
        plan.success_criteria = ["Task completed", "Results verified"]
        return plan

    def _replan_fallback(self, plan: Plan, failed_step: PlanStep, error: str) -> Plan:
        retry_step = PlanStep(
            id=f"{failed_step.id}_retry_{failed_step.attempt_count + 1}",
            plan_id=plan.id,
            objective=f"Retry: {failed_step.objective}",
            dependencies=[d for d in failed_step.dependencies if d != failed_step.id],
            required_tools=failed_step.required_tools[:],
            required_capabilities=failed_step.required_capabilities[:],
            verification_criteria=failed_step.verification_criteria[:],
            metadata={"replan_of": failed_step.id, "error": error},
        )

        failed_step.status = StepStatus.REPLANNED
        failed_step.updated_at = time.time()

        plan.insert_step_after(failed_step.id, retry_step)
        return plan

    def _apply_replan(self, plan: Plan, failed_step: PlanStep, data: dict[str, Any]) -> Plan:
        failed_step.status = StepStatus.REPLANNED
        failed_step.updated_at = time.time()

        for step_data in data.get("revised_steps", []):
            step = PlanStep(
                id=step_data.get("id", f"replan_{plan.replan_count}_{len(plan.steps) + 1}"),
                plan_id=plan.id,
                objective=step_data.get("objective", ""),
                dependencies=step_data.get("dependencies", []),
                required_tools=step_data.get("required_tools", []),
                required_capabilities=step_data.get("required_capabilities", []),
                verification_criteria=step_data.get("verification_criteria", []),
                metadata={"replan_of": failed_step.id},
            )
            plan.add_step(step)

        return plan
