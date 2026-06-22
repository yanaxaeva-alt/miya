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


def test_graph_run_resumes_after_approval(tmp_path: Path) -> None:
    """Approved graphs continue through remaining nodes."""
    runner = GraphRunner(
        provider=MockModelProvider(),
        checkpoint_store=CheckpointStore(tmp_path / "checkpoints.sqlite3"),
        decision_log=DecisionLog(tmp_path / "decisions.jsonl"),
    )
    graph = _graph_with_approval()
    initial = runner.run(graph, input_text="publish a post")

    resumed = runner.resume(
        graph,
        input_text="publish a post",
        outputs=dict(initial.outputs),
        after_node_id="Approval",
        run_id=initial.run_id,
        trace_id=initial.trace_id,
    )

    assert initial.status == "waiting_for_approval"
    assert resumed.status == "completed"
    assert resumed.outputs["END"].startswith("approved:")
    assert resumed.events[-1].event_type == GraphEventType.RUN_COMPLETED


def test_graph_tool_node_executes_sandbox_mock(tmp_path: Path) -> None:
    """Tool nodes invoke sandbox registry tools through the Policy Gate."""
    runner = GraphRunner(
        provider=MockModelProvider(),
        checkpoint_store=CheckpointStore(tmp_path / "checkpoints.sqlite3"),
        decision_log=DecisionLog(tmp_path / "decisions.jsonl"),
    )
    graph = AgentGraphSpec.model_validate(
        {
            "graph_id": "tool-graph",
            "name": "Tool graph",
            "nodes": [
                {"id": "START", "type": "input"},
                {"id": "Search", "type": "tool", "config": {"tool_name": "web_search_mock"}},
                {"id": "END", "type": "output"},
            ],
            "edges": [
                {"source": "START", "target": "Search"},
                {"source": "Search", "target": "END"},
            ],
        }
    )

    run = runner.run(graph, input_text="Mia sandbox search")

    assert run.status == "completed"
    assert "[mock-search]" in run.outputs["Search"]
    assert GraphEventType.TOOL_INVOKED in [event.event_type for event in run.events]
