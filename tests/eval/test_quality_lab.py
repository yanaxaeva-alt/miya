"""Deterministic tests for the Quality Lab MVP."""

from pathlib import Path

import pytest

from miaos.executor import AgentGraphSpec, CheckpointStore, GraphRunner
from miaos.models import MockModelProvider
from miaos.observability import DecisionLog
from miaos.persona import PersonaPackage, create_persona_package, load_persona_package
from miaos.quality import (
    EvalCategory,
    GoldenDataset,
    GraphRegressionEval,
    PersonaConsistencyEval,
    SafetyBoundaryEval,
)
from miaos.runtime.chat import ChatSession

pytestmark = pytest.mark.eval

GOLDEN_PATH = Path("evals/golden/mia_mvp.jsonl")


def _create_package(tmp_path: Path) -> PersonaPackage:
    """Create a minimal persona package for evals."""
    profile = tmp_path / "persona.yaml"
    output = tmp_path / "mia"
    profile.write_text(
        """
identity:
  role: Quality Lab persona
values:
  ranked: [honesty, care]
model_binding:
  provider: mock
  model_id: mock-quality
autonomy_contract:
  contract_id: quality-contract
  autonomy_ceiling: L3
""".strip(),
        encoding="utf-8",
    )
    create_persona_package(name="Mia", profile_path=profile, output_path=output)
    return load_persona_package(output)


def _graph() -> AgentGraphSpec:
    """Create a graph with approval boundary."""
    return AgentGraphSpec.model_validate(
        {
            "graph_id": "quality-graph",
            "name": "Quality graph",
            "nodes": [
                {"id": "START", "type": "input"},
                {"id": "Planner", "type": "llm", "config": {"prompt": "Plan"}},
                {"id": "Approval", "type": "approval", "config": {"action_class": "publish"}},
                {"id": "END", "type": "output"},
            ],
            "edges": [
                {"source": "START", "target": "Planner"},
                {"source": "Planner", "target": "Approval"},
                {"source": "Approval", "target": "END"},
            ],
        }
    )


def test_golden_dataset_loads_and_groups_cases() -> None:
    """Golden dataset JSONL loads with all MVP eval categories."""
    dataset = GoldenDataset.from_jsonl(GOLDEN_PATH)

    assert dataset.by_category(EvalCategory.PERSONA_CONSISTENCY)
    assert dataset.by_category(EvalCategory.SAFETY_BOUNDARY)
    assert dataset.by_category(EvalCategory.GRAPH_REGRESSION)


def test_persona_consistency_eval_passes_minimal_persona(tmp_path: Path) -> None:
    """Persona consistency eval validates immutable persona anchors."""
    dataset = GoldenDataset.from_jsonl(GOLDEN_PATH)
    report = PersonaConsistencyEval(persona=_create_package(tmp_path)).run(dataset.cases)

    assert report.passed is True
    assert report.results[0].details["missing_markers"] == ""
    assert report.results[0].details["forbidden_terms"] == ""


def test_safety_boundary_eval_blocks_forbidden_intent(tmp_path: Path) -> None:
    """Safety eval proves denied-always intent is blocked and audited."""
    dataset = GoldenDataset.from_jsonl(GOLDEN_PATH)
    log = DecisionLog(tmp_path / "decisions.jsonl")
    session = ChatSession(
        persona=_create_package(tmp_path),
        provider=MockModelProvider(),
        decision_log=log,
    )

    report = SafetyBoundaryEval(session=session).run(dataset.cases)

    assert report.passed is True
    assert log.verify_integrity() is True
    assert log.list_events()


def test_graph_regression_eval_matches_status_and_events(tmp_path: Path) -> None:
    """Graph regression eval validates status and event sequence."""
    dataset = GoldenDataset.from_jsonl(GOLDEN_PATH)
    runner = GraphRunner(
        provider=MockModelProvider(),
        checkpoint_store=CheckpointStore(tmp_path / "checkpoints.sqlite3"),
        decision_log=DecisionLog(tmp_path / "decisions.jsonl"),
    )

    report = GraphRegressionEval(graph=_graph(), runner=runner).run(dataset.cases)

    assert report.passed is True
    assert report.results[0].details["actual_status"] == "waiting_for_approval"
