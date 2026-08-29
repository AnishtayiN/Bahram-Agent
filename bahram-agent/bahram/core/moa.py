"""Mixture of Agents for Bahram Agent."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Optional, Callable

logger = logging.getLogger(__name__)


@dataclass
class AgentConfig:
    """Configuration for a MoA agent."""

    name: str
    model: str = ""
    provider: str = ""
    role: str = ""  # proposer, verifier, aggregator
    temperature: float = 0.7
    max_tokens: int = 4096


@dataclass
class MoAResult:
    """Result from MoA processing."""

    final_response: str
    agent_responses: list[dict[str, str]] = field(default_factory=list)
    rounds: int = 0
    consensus_reached: bool = False


class MixtureOfAgents:
    """Mixture of Agents - orchestrate multiple LLMs."""

    def __init__(self) -> None:
        self._agents: list[AgentConfig] = []
        self._proposer_count: int = 3
        self._verifier_count: int = 2
        self._aggregator_count: int = 1

    def add_agent(self, config: AgentConfig) -> None:
        """Add an agent to the mix."""
        self._agents.append(config)

    def set_topology(
        self,
        proposers: int = 3,
        verifiers: int = 2,
        aggregators: int = 1,
    ) -> None:
        """Set the MoA topology."""
        self._proposer_count = proposers
        self._verifier_count = verifiers
        self._aggregator_count = aggregators

    async def process(
        self,
        prompt: str,
        llm_fn: Callable,
        rounds: int = 2,
    ) -> MoAResult:
        """Process a prompt through MoA.

        Args:
            prompt: The input prompt
            llm_fn: Async function that takes (model, prompt) and returns response
            rounds: Number of refinement rounds

        Returns:
            MoAResult with final response
        """
        result = MoAResult(final_response="")

        # Phase 1: Proposers generate initial responses
        proposer_responses = []
        for i in range(self._proposer_count):
            agent = self._get_agent("proposer", i)
            if agent:
                response = await llm_fn(agent.model, prompt)
                proposer_responses.append({
                    "agent": agent.name,
                    "response": response,
                })
                result.agent_responses.append({
                    "agent": agent.name,
                    "phase": "proposer",
                    "response": response[:200],
                })

        if not proposer_responses:
            return result

        # Phase 2: Refinement rounds
        current_responses = [r["response"] for r in proposer_responses]

        for round_num in range(rounds):
            result.rounds = round_num + 1

            # Verifiers review and critique
            verifier_feedback = []
            for i in range(self._verifier_count):
                agent = self._get_agent("verifier", i)
                if agent:
                    combined = "\n\n".join(
                        f"Response {j+1}:\n{r}" for j, r in enumerate(current_responses)
                    )
                    critique_prompt = f"Review these responses and identify strengths/weaknesses:\n\n{combined}"
                    response = await llm_fn(agent.model, critique_prompt)
                    verifier_feedback.append(response)

            # Proposers refine based on feedback
            if verifier_feedback:
                feedback_summary = "\n\n".join(verifier_feedback)
                refined = []
                for i in range(self._proposer_count):
                    agent = self._get_agent("proposer", i)
                    if agent:
                        refine_prompt = f"Original prompt: {prompt}\n\nFeedback:\n{feedback_summary}\n\nProvide an improved response:"
                        response = await llm_fn(agent.model, refine_prompt)
                        refined.append(response)
                current_responses = refined

        # Phase 3: Aggregator synthesizes final response
        aggregator = self._get_agent("aggregator", 0)
        if aggregator:
            combined = "\n\n".join(
                f"Response {i+1}:\n{r}" for i, r in enumerate(current_responses)
            )
            aggregate_prompt = f"Synthesize these responses into one best response:\n\n{combined}"
            result.final_response = await llm_fn(aggregator.model, aggregate_prompt)
            result.consensus_reached = True
        elif current_responses:
            result.final_response = current_responses[0]

        return result

    def _get_agent(self, role: str, index: int) -> Optional[AgentConfig]:
        """Get an agent by role and index."""
        role_agents = [a for a in self._agents if a.role == role]
        if index < len(role_agents):
            return role_agents[index]
        # Fallback: use any available agent
        if self._agents:
            return self._agents[index % len(self._agents)]
        return None

    def list_agents(self) -> list[dict]:
        """List all agents."""
        return [
            {"name": a.name, "model": a.model, "role": a.role}
            for a in self._agents
        ]
