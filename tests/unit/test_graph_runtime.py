"""Tests for AgentGraph validation and execution."""

from pathlib import Path

import pytest

from miaos.executor import (
    AgentGraphSpec,
    CheckpointStore,
    GraphEventType,
    GraphRunner,
    NodeType,
)
from miaos.models import MockModelProvider
from miaos.observability import DecisionLog


def _graph_with_approval(action_class: str = "publish") -> AgentGraphSpec:
    """Create a minimal graph with an approval node."""
    return AgentGraphSpec.model_validate(
        {
            "graph_id": "test-graph",
            "name": "Test graph",
            "nodes": [
                {"id": "START", "type": "input"},
                {"id": "Planner", "type": "llm", "config": {"prompt": "Plan"}},
                {"id": "Critic", "type": "critic"},
                {"id": "Approval", "type": "approval", "config": {"action_class": action_class}},
                {"id": "END", "type": "output"},
            ],
            "edges": [
                {"source": "START", "target": "Planner"},
                {"source": "Planner", "target": "Critic"},
                {"source": "Critic", "target": "Approval"},
                {"source": "Approval", "target": "END"},
            ],
        }
    )


def test_graph_validation_accepts_valid_dag() -> None:
    """A valid graph produces typed nodes."""
    graph = _graph_with_approval()

    assert graph.node_by_id("START").type == NodeType.INPUT
    assert graph.node_by_id("END").type == NodeType.OUTPUT


def test_graph_validation_accepts_tool_and_memory_nodes() -> None:
    """Visual graph node vocabulary includes safe tool and memory nodes."""
    graph = AgentGraphSpec.model_validate(
        {
            "graph_id": "tool-memory",
            "name": "Tool memory graph",
            "nodes": [
                {"id": "START", "type": "input"},
                {"id": "Tool", "type": "tool", "config": {"action_class": "read"}},
                {"id": "Memory", "type": "memory"},
                {"id": "END", "type": "output"},
            ],
            "edges": [
                {"source": "START", "target": "Tool"},
                {"source": "Tool", "target": "Memory"},
                {"source": "Memory", "target": "END"},
            ],
        }
    )

    assert graph.node_by_id("Tool").type == NodeType.TOOL
    assert graph.node_by_id("Memory").type == NodeType.MEMORY


def test_graph_validation_rejects_cycles() -> None:
    """Cyclic graphs fail validation."""
    with pytest.raises(ValueError, match="acyclic"):
        AgentGraphSpec.model_validate(
            {
                "graph_id": "cycle",
                "name": "Cycle",
                "nodes": [
                    {"id": "A", "type": "input"},
                    {"id": "B", "type": "output"},
                ],
                "edges": [
                    {"source": "A", "target": "B"},
                    {"source": "B", "target": "A"},
                ],
            }
        )


def test_graph_run_with_mock_provider_emits_ordered_events(tmp_path: Path) -> None:
    """Graph execution emits start, node, approval, and stop events."""
    runner = GraphRunner(
        provider=MockModelProvider(),
        checkpoint_store=CheckpointStore(tmp_path / "checkpoints.sqlite3"),
        decision_log=DecisionLog(tmp_path / "decisions.jsonl"),
    )

    run = runner.run(_graph_with_approval(), input_text="draft a post")
    event_types = [event.event_type for event in run.events]

    assert run.status == "waiting_for_approval"
    assert event_types[0] == GraphEventType.RUN_STARTED
    assert GraphEventType.APPROVAL_REQUIRED in event_types
    assert event_types[-1] == GraphEventType.RUN_STOPPED
    assert (tmp_path / "decisions.jsonl").exists()


def test_checkpoint_store_persists_graph_events(tmp_path: Path) -> None:
    """Graph events are persisted to the checkpoint store."""
    checkpoint_store = CheckpointStore(tmp_path / "checkpoints.sqlite3")
    runner = GraphRunner(
        provider=MockModelProvider(),
        checkpoint_store=checkpoint_store,
        decision_log=DecisionLog(tmp_path / "decisions.jsonl"),
    )

    run = runner.run(_graph_with_approval(), input_text="draft a post")
    persisted = checkpoint_store.list_events(run.run_id)

    assert [event.event_type for event in persisted] == [event.event_type for event in run.events]


def test_approval_node_stops_external_action(tmp_path: Path) -> None:
    """Approval nodes create approval requests instead of executing external actions."""
    runner = GraphRunner(
        provider=MockModelProvider(),
        checkpoint_store=CheckpointStore(tmp_path / "checkpoints.sqlite3"),
        decision_log=DecisionLog(tmp_path / "decisions.jsonl"),
    )

    run = runner.run(_graph_with_approval("publish"), input_text="publish a post")

    assert run.status == "waiting_for_approval"
    assert run.outputs["Approval"] == "approval_request:require_approval:publish"
    assert DecisionLog(tmp_path / "decisions.jsonl").verify_integrity() is True


def test_tool_node_blocks_dangerous_action_without_side_effects(tmp_path: Path) -> None:
    """Tool nodes pass Policy Gate and stop dangerous actions in mock runs."""
    graph = AgentGraphSpec.model_validate(
        {
            "graph_id": "blocked-tool",
            "name": "Blocked tool",
            "nodes": [
                {"id": "START", "type": "input"},
                {
                    "id": "Danger",
                    "type": "tool",
                    "config": {
                        "tool_name": "finance_stub",
                        "action_class": "financial_transaction",
                    },
                },
                {"id": "END", "type": "output"},
            ],
            "edges": [
                {"source": "START", "target": "Danger"},
                {"source": "Danger", "target": "END"},
            ],
        }
    )
    runner = GraphRunner(
        provider=MockModelProvider(),
        checkpoint_store=CheckpointStore(tmp_path / "checkpoints.sqlite3"),
        decision_log=DecisionLog(tmp_path / "decisions.jsonl"),
    )

    run = runner.run(graph, input_text="wire money")

    assert run.status == "waiting_for_approval"
    assert run.outputs["Danger"] == "tool_blocked:deny:financial_transaction"
    assert not (tmp_path / "finance.txt").exists()
    assert DecisionLog(tmp_path / "decisions.jsonl").verify_integrity() is True
