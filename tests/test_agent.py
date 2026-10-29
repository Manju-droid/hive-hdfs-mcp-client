"""Tests for LangGraph agent interaction helpers."""

import asyncio
from types import SimpleNamespace

from agents.hive_agent import ask


class FakeAgent:
    def __init__(self) -> None:
        self.calls: list[tuple[dict, dict]] = []

    async def ainvoke(self, input: dict, config: dict) -> dict:
        self.calls.append((input, config))
        question = input["messages"][0]["content"]
        return {"messages": [SimpleNamespace(content=f"Answer: {question}")]}


def test_ask_preserves_thread_and_returns_agent_answer() -> None:
    async def exercise() -> None:
        graph = FakeAgent()
        first = await ask(graph, "How many transactions?", "session-1", 10)
        follow_up = await ask(graph, "And flagged?", "session-1", 10)

        assert first == "Answer: How many transactions?"
        assert follow_up == "Answer: And flagged?"
        assert [
            call[1]["configurable"]["thread_id"] for call in graph.calls
        ] == ["session-1", "session-1"]

    asyncio.run(exercise())
