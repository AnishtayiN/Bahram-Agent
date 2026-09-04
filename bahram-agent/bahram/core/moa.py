from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class AgentConfig:
    name: str
    model: str = ""
    provider: str = ""
    role: str = ""
    temperature: float = 0.7
    max_tokens: int = 4096


@dataclass
class MoAResult:
    final_response: str
    agent_responses: list[dict[str, str]] = field(default_factory=list)
    rounds: int = 0
    consensus_reached: bool = False


class MixtureOfAgents:
    def __init__(self) -> None:
        self._agents: list[AgentConfig] = []
        self._proposer_count: int = 3
        self._verifier_count: int = 2
        self._aggregator_count: int = 1

    def add_agent(self, config: AgentConfig) -> None:
        self._agents.append(config)

    def set_topology(
        self,
        proposers: int = 3,
        verifiers: int = 2,
        aggregators: int = 1,
    ) -> None:
        self._proposer_count = proposers
        self._verifier_count = verifiers
        self._aggregator_count = aggregators

    async def process(
        self,
        prompt: str,
        llm_fn: Callable,
        rounds: int = 2,
    ) -> MoAResult:
        result = MoAResult(final_response="")

        proposer_responses = []
        for i in range(self._proposer_count):
            agent = self._get_agent("proposer", i)
            if agent:
                response = await llm_fn(agent.model, prompt)
                proposer_responses.append(
                    {
                        "agent": agent.name,
                        "response": response,
                    }
                )
                result.agent_responses.append(
                    {
                        "agent": agent.name,
                        "phase": "proposer",
                        "response": response[:200],
                    }
                )

        if not proposer_responses:
            return result

        current_responses = [r["response"] for r in proposer_responses]

        for round_num in range(rounds):
            result.rounds = round_num + 1

            verifier_feedback = []
            for i in range(self._verifier_count):
                agent = self._get_agent("verifier", i)
                if agent:
                    combined = "\n\n".join(
                        f"Response {j + 1}:\n{r}" for j, r in enumerate(current_responses)
                    )
                    critique_prompt = (
                        f"Review these responses and identify strengths/weaknesses:\n\n{combined}"
                    )
                    response = await llm_fn(agent.model, critique_prompt)
                    verifier_feedback.append(response)

            if verifier_feedback:
                feedback_summary = "\n\n".join(verifier_feedback)
                refined = []
                for i in range(self._proposer_count):
                    agent = self._get_agent("proposer", i)
                    if agent:
                        refine_prompt = (
                            f"Original prompt: {prompt}\n\nFeedback:\n"
                            f"{feedback_summary}\n\nProvide an improved response:"
                        )
                        response = await llm_fn(agent.model, refine_prompt)
                        refined.append(response)
                current_responses = refined

        aggregator = self._get_agent("aggregator", 0)
        if aggregator:
            combined = "\n\n".join(
                f"Response {i + 1}:\n{r}" for i, r in enumerate(current_responses)
            )
            aggregate_prompt = f"Synthesize these responses into one best response:\n\n{combined}"
            result.final_response = await llm_fn(aggregator.model, aggregate_prompt)
            result.consensus_reached = True
        elif current_responses:
            result.final_response = current_responses[0]

        return result

    def _get_agent(self, role: str, index: int) -> AgentConfig | None:
        role_agents = [a for a in self._agents if a.role == role]
        if index < len(role_agents):
            return role_agents[index]

        if self._agents:
            return self._agents[index % len(self._agents)]
        return None

    def list_agents(self) -> list[dict]:
        return [{"name": a.name, "model": a.model, "role": a.role} for a in self._agents]
