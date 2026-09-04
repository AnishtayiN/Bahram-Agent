"""
Budget.

Public objects: ``BudgetConfig``, ``BudgetUsage``, ``BudgetManager``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from bahram.autonomy.cost import estimate_cost

logger = logging.getLogger(__name__)


@dataclass
class BudgetConfig:
    """
    Budget config.

    Attributes:
        max_input_tokens (int): numeric value for max input tokens.
        max_output_tokens (int): numeric value for max output tokens.
        max_total_tokens (int): numeric value for max total tokens.
        max_cost_usd (float): numeric value for max cost usd.
        max_model_calls (int): numeric value for max model calls.
        max_tool_calls (int): numeric value for max tool calls.
        max_subagent_calls (int): numeric value for max subagent calls.
        warning_threshold (float): numeric value for warning threshold.
    """

    max_input_tokens: int = 100000
    max_output_tokens: int = 50000
    max_total_tokens: int = 150000
    max_cost_usd: float = 5.0
    max_model_calls: int = 50
    max_tool_calls: int = 100
    max_subagent_calls: int = 10
    warning_threshold: float = 0.8

    def to_dict(self) -> dict[str, Any]:
        """
        Serialise the object to a JSON-serialisable dictionary.

        Returns:
            dict[str, Any]: a mapping of str, Any.
        """
        return {
            "max_input_tokens": self.max_input_tokens,
            "max_output_tokens": self.max_output_tokens,
            "max_total_tokens": self.max_total_tokens,
            "max_cost_usd": self.max_cost_usd,
            "max_model_calls": self.max_model_calls,
            "max_tool_calls": self.max_tool_calls,
            "max_subagent_calls": self.max_subagent_calls,
            "warning_threshold": self.warning_threshold,
        }


@dataclass
class BudgetUsage:
    """
    Budget usage.

    Attributes:
        input_tokens (int): numeric value for input tokens.
        output_tokens (int): numeric value for output tokens.
        total_tokens (int): numeric value for total tokens.
        estimated_cost_usd (float): numeric value for estimated cost usd.
        cost_usd (float): numeric value for cost usd.
        model_calls (int): numeric value for model calls.
        tool_calls (int): numeric value for tool calls.
        subagent_calls (int): numeric value for subagent calls.
        warnings (list[str]): collection of warnings.
    """

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0
    cost_usd: float = 0.0
    model_calls: int = 0
    tool_calls: int = 0
    subagent_calls: int = 0
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """
        Serialise the object to a JSON-serialisable dictionary.

        Returns:
            dict[str, Any]: a mapping of str, Any.
        """
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "estimated_cost_usd": self.estimated_cost_usd,
            "cost_usd": self.cost_usd,
            "model_calls": self.model_calls,
            "tool_calls": self.tool_calls,
            "subagent_calls": self.subagent_calls,
            "warnings": self.warnings,
        }


class BudgetManager:
    """
    Budget manager.
    """

    def __init__(self, config: BudgetConfig | None = None) -> None:
        """
        Initialise a BudgetManager instance.

        Args:
            config (BudgetConfig | None): configuration object. Defaults to ``None``.
        """
        self._config = config or BudgetConfig()
        self._session_budgets: dict[str, BudgetUsage] = {}
        self._run_budgets: dict[str, BudgetUsage] = {}
        self._step_budgets: dict[str, BudgetUsage] = {}
        self._subagent_budgets: dict[str, BudgetUsage] = {}

    @property
    def config(self) -> BudgetConfig:
        """
        Config.

        Returns:
            BudgetConfig: the resulting BudgetConfig.
        """
        return self._config

    def get_session_budget(self, session_id: str) -> BudgetUsage:
        """
        Return the session budget.

        Args:
            session_id (str): session identifier.

        Returns:
            BudgetUsage: the resulting BudgetUsage.
        """
        if session_id not in self._session_budgets:
            self._session_budgets[session_id] = BudgetUsage()
        return self._session_budgets[session_id]

    def get_run_budget(self, run_id: str) -> BudgetUsage:
        """
        Return the run budget.

        Args:
            run_id (str): run identifier.

        Returns:
            BudgetUsage: the resulting BudgetUsage.
        """
        if run_id not in self._run_budgets:
            self._run_budgets[run_id] = BudgetUsage()
        return self._run_budgets[run_id]

    def get_step_budget(self, step_id: str) -> BudgetUsage:
        """
        Return the step budget.

        Args:
            step_id (str): plan-step identifier.

        Returns:
            BudgetUsage: the resulting BudgetUsage.
        """
        if step_id not in self._step_budgets:
            self._step_budgets[step_id] = BudgetUsage()
        return self._step_budgets[step_id]

    def get_subagent_budget(self, task_id: str) -> BudgetUsage:
        """
        Return the subagent budget.

        Args:
            task_id (str): task identifier.

        Returns:
            BudgetUsage: the resulting BudgetUsage.
        """
        if task_id not in self._subagent_budgets:
            self._subagent_budgets[task_id] = BudgetUsage()
        return self._subagent_budgets[task_id]

    def record_model_call(
        self,
        run_id: str,
        session_id: str = "",
        input_tokens: int = 0,
        output_tokens: int = 0,
        *,
        model: str = "",
    ) -> list[str]:
        """
        Record model call.

        Args:
            run_id (str): run identifier.
            session_id (str): session identifier. Defaults to ``''``.
            input_tokens (int): numeric value for input tokens. Defaults to ``0``.
            output_tokens (int): numeric value for output tokens. Defaults to ``0``.
            model (str): model identifier in ``provider/model`` form. Defaults to ``''``.

        Returns:
            list[str]: a sequence of str entries (empty when there is nothing to report).
        """
        warnings = []

        cost = estimate_cost(model, input_tokens, output_tokens) if model else 0.0

        run_budget = self.get_run_budget(run_id)
        run_budget.input_tokens += input_tokens
        run_budget.output_tokens += output_tokens
        run_budget.total_tokens += input_tokens + output_tokens
        run_budget.estimated_cost_usd += cost
        run_budget.cost_usd += cost
        run_budget.model_calls += 1

        if session_id:
            session_budget = self.get_session_budget(session_id)
            session_budget.input_tokens += input_tokens
            session_budget.output_tokens += output_tokens
            session_budget.total_tokens += input_tokens + output_tokens
            session_budget.estimated_cost_usd += cost
            session_budget.cost_usd += cost
            session_budget.model_calls += 1

            if (
                session_budget.total_tokens
                >= self._config.max_total_tokens * self._config.warning_threshold
            ):
                w = (
                    f"Session token usage at "
                    f"{session_budget.total_tokens}/{self._config.max_total_tokens}"
                )
                warnings.append(w)
                session_budget.warnings.append(w)

        if (
            run_budget.total_tokens
            >= self._config.max_total_tokens * self._config.warning_threshold
        ):
            w = f"Run token usage at {run_budget.total_tokens}/{self._config.max_total_tokens}"
            warnings.append(w)
            run_budget.warnings.append(w)

        if run_budget.model_calls >= self._config.max_model_calls * self._config.warning_threshold:
            w = f"Run model calls at {run_budget.model_calls}/{self._config.max_model_calls}"
            warnings.append(w)
            run_budget.warnings.append(w)

        if (
            run_budget.estimated_cost_usd
            >= self._config.max_cost_usd * self._config.warning_threshold
        ):
            w = f"Run cost at ${run_budget.estimated_cost_usd:.4f}/${self._config.max_cost_usd:.2f}"
            warnings.append(w)
            run_budget.warnings.append(w)

        if session_id:
            if (
                session_budget.estimated_cost_usd
                >= self._config.max_cost_usd * self._config.warning_threshold
            ):
                w = (
                    f"Session cost at "
                    f"${session_budget.estimated_cost_usd:.4f}/${self._config.max_cost_usd:.2f}"
                )
                warnings.append(w)
                session_budget.warnings.append(w)

        return warnings

    def record_tool_call(self, run_id: str, session_id: str = "", tool_name: str = "") -> list[str]:
        """Record one tool call against the run budget.

        Args:
            run_id (str): run identifier.
            session_id (str): session identifier. Defaults to ``''``.
            tool_name (str): name of the tool that ran. Recorded in the
                warning message so an operator can see which tool is hot; it
                does not change the accounting. ``AgentEngine.run`` passes it
                as a keyword argument, which this signature used to reject -
                every run that called a tool with a budget manager wired
                crashed with ``TypeError: ... unexpected keyword argument
                'tool_name'``.

        Returns:
            list[str]: a sequence of str entries (empty when there is nothing to report).
        """
        warnings = []

        run_budget = self.get_run_budget(run_id)
        run_budget.tool_calls += 1
        if tool_name:
            run_budget.warnings.append(f"tool:{tool_name}")

        if run_budget.tool_calls >= self._config.max_tool_calls * self._config.warning_threshold:
            w = f"Run tool calls at {run_budget.tool_calls}/{self._config.max_tool_calls}"
            warnings.append(w)
            run_budget.warnings.append(w)

        return warnings

    def record_subagent_call(self, run_id: str) -> list[str]:
        """
        Record subagent call.

        Args:
            run_id (str): run identifier.

        Returns:
            list[str]: a sequence of str entries (empty when there is nothing to report).
        """
        warnings = []

        run_budget = self.get_run_budget(run_id)
        run_budget.subagent_calls += 1

        if (
            run_budget.subagent_calls
            >= self._config.max_subagent_calls * self._config.warning_threshold
        ):
            w = (
                f"Run subagent calls at "
                f"{run_budget.subagent_calls}/{self._config.max_subagent_calls}"
            )
            warnings.append(w)
            run_budget.warnings.append(w)

        return warnings

    def check_budget(self, run_id: str, session_id: str = "") -> dict[str, Any]:
        """
        Check budget.

        Args:
            run_id (str): run identifier.
            session_id (str): session identifier. Defaults to ``''``.

        Returns:
            dict[str, Any]: a mapping of str, Any.
        """
        run_budget = self.get_run_budget(run_id)
        exceeded = []

        if run_budget.total_tokens >= self._config.max_total_tokens:
            exceeded.append("total_tokens")
        if run_budget.model_calls >= self._config.max_model_calls:
            exceeded.append("model_calls")
        if run_budget.tool_calls >= self._config.max_tool_calls:
            exceeded.append("tool_calls")
        if run_budget.subagent_calls >= self._config.max_subagent_calls:
            exceeded.append("subagent_calls")
        if run_budget.estimated_cost_usd >= self._config.max_cost_usd:
            exceeded.append("cost_usd")

        return {
            "exceeded": exceeded,
            "can_continue": len(exceeded) == 0,
            "run_usage": run_budget.to_dict(),
            "config": self._config.to_dict(),
        }

    def check_cost_budget(self, run_id: str, max_cost: float | None = None) -> dict[str, Any]:
        """Check cost-specific budget limits for a run.

        Returns dict with cost status, warnings, and whether hard limit is hit.
        """
        run_budget = self.get_run_budget(run_id)
        limit = max_cost if max_cost is not None else self._config.max_cost_usd
        cost = run_budget.estimated_cost_usd
        warning_limit = limit * self._config.warning_threshold
        soft_limit = limit
        hard_limit = limit * 1.2

        warnings = []
        if cost >= warning_limit:
            warnings.append(f"Cost approaching limit: ${cost:.4f} / ${limit:.2f}")

        hard_exceeded = cost >= hard_limit
        soft_exceeded = cost >= soft_limit

        return {
            "cost_usd": cost,
            "warning_limit": warning_limit,
            "soft_limit": soft_limit,
            "hard_limit": hard_limit,
            "soft_exceeded": soft_exceeded,
            "hard_exceeded": hard_exceeded,
            "warnings": warnings,
            "can_continue": not hard_exceeded,
        }

    def reset_run(self, run_id: str) -> None:
        """
        Reset run.

        Args:
            run_id (str): run identifier.
        """
        self._run_budgets.pop(run_id, None)

    def reset_session(self, session_id: str) -> None:
        """
        Reset session.

        Args:
            session_id (str): session identifier.
        """
        self._session_budgets.pop(session_id, None)

    def get_all_usage(self) -> dict[str, Any]:
        """
        Return the all usage.

        Returns:
            dict[str, Any]: a mapping of str, Any.
        """
        return {
            "sessions": {k: v.to_dict() for k, v in self._session_budgets.items()},
            "runs": {k: v.to_dict() for k, v in self._run_budgets.items()},
        }
