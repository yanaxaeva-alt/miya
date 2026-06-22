"""Deterministic Quality Lab eval runner."""

from pathlib import Path

from pydantic import BaseModel, Field

from miaos.executor import AgentGraphSpec, CheckpointStore, GraphRunner
from miaos.models.providers import ModelProvider, resolve_provider
from miaos.observability import DecisionLog
from miaos.persona import load_persona_package
from miaos.quality.datasets import GoldenCase, GoldenDataset
from miaos.runtime.chat import ChatSession


class EvalResult(BaseModel):
    """Result for one golden case."""

    case_id: str
    suite: str
    passed: bool
    detail: str


class EvalReport(BaseModel):
    """Aggregate report for one dataset run."""

    dataset: str
    provider: str
    passed: int
    failed: int
    pass_rate: float
    min_pass_rate: float
    gate_passed: bool
    results: list[EvalResult] = Field(default_factory=list)


def run_quality_eval(
    dataset: GoldenDataset,
    *,
    provider_name: str,
    persona_dir: Path,
    package_id: str,
    decision_log: DecisionLog,
    checkpoint_store: CheckpointStore,
) -> EvalReport:
    """Run all cases in a dataset with the selected provider."""
    provider = resolve_provider(provider_name)
    results: list[EvalResult] = []

    for case in dataset.cases:
        try:
            passed, detail = _run_case(
                case,
                provider_name=provider_name,
                provider=provider,
                persona_dir=persona_dir,
                package_id=package_id,
                decision_log=decision_log,
                checkpoint_store=checkpoint_store,
            )
        except Exception as exc:  # noqa: BLE001 — eval runner captures per-case failures
            passed = False
            detail = str(exc)

        results.append(
            EvalResult(
                case_id=case.id,
                suite=case.suite,
                passed=passed,
                detail=detail,
            )
        )

    passed_count = sum(1 for result in results if result.passed)
    failed_count = len(results) - passed_count
    pass_rate = passed_count / len(results) if results else 0.0

    return EvalReport(
        dataset=dataset.name,
        provider=provider_name,
        passed=passed_count,
        failed=failed_count,
        pass_rate=pass_rate,
        min_pass_rate=dataset.min_pass_rate,
        gate_passed=pass_rate >= dataset.min_pass_rate,
        results=results,
    )


def _run_case(
    case: GoldenCase,
    *,
    provider_name: str,
    provider: ModelProvider,
    persona_dir: Path,
    package_id: str,
    decision_log: DecisionLog,
    checkpoint_store: CheckpointStore,
) -> tuple[bool, str]:
    if case.suite == "persona_consistency":
        return _eval_persona_consistency(
            case,
            provider=provider,
            provider_name=provider_name,
            persona_dir=persona_dir,
            package_id=package_id,
            decision_log=decision_log,
        )
    if case.suite == "safety_boundary":
        return _eval_safety_boundary(
            case,
            provider=provider,
            persona_dir=persona_dir,
            package_id=package_id,
            decision_log=decision_log,
        )
    if case.suite == "graph_regression":
        return _eval_graph_regression(
            case,
            provider_name=provider_name,
            decision_log=decision_log,
            checkpoint_store=checkpoint_store,
        )
    msg = f"unsupported suite: {case.suite}"
    raise ValueError(msg)


def _eval_persona_consistency(
    case: GoldenCase,
    *,
    provider: ModelProvider,
    provider_name: str,
    persona_dir: Path,
    package_id: str,
    decision_log: DecisionLog,
) -> tuple[bool, str]:
    message = str(case.input.get("message", ""))
    expect_substring = str(case.input.get("expect_substring", ""))
    expect_blocked = bool(case.input.get("expect_blocked", False))

    persona = load_persona_package(persona_dir / package_id)
    session = ChatSession(persona=persona, provider=provider, decision_log=decision_log)
    turn = session.run_turn(message)

    if turn.blocked != expect_blocked:
        return False, f"blocked={turn.blocked}, expected {expect_blocked}"

    if provider_name == "mock":
        if expect_substring and expect_substring not in turn.response_text:
            return False, f"response missing substring: {expect_substring!r}"
    elif not turn.response_text.strip():
        return False, "empty response from provider"

    return True, turn.response_text[:120]


def _eval_safety_boundary(
    case: GoldenCase,
    *,
    provider: ModelProvider,
    persona_dir: Path,
    package_id: str,
    decision_log: DecisionLog,
) -> tuple[bool, str]:
    message = str(case.input.get("message", ""))
    expect_blocked = bool(case.input.get("expect_blocked", True))

    persona = load_persona_package(persona_dir / package_id)
    session = ChatSession(persona=persona, provider=provider, decision_log=decision_log)
    turn = session.run_turn(message)

    if turn.blocked != expect_blocked:
        return False, f"blocked={turn.blocked}, expected {expect_blocked}"
    if expect_blocked and "Blocked by Policy Gate" not in turn.response_text:
        return False, "expected Policy Gate block message"
    return True, turn.policy_decision.decision.value


def _eval_graph_regression(
    case: GoldenCase,
    *,
    provider_name: str,
    decision_log: DecisionLog,
    checkpoint_store: CheckpointStore,
) -> tuple[bool, str]:
    graph_payload = case.input.get("graph")
    if not isinstance(graph_payload, dict):
        return False, "case input.graph must be an object"

    input_text = str(case.input.get("input_text", "test"))
    expect_status = str(case.input.get("expect_status", "completed"))

    graph = AgentGraphSpec.model_validate(graph_payload)
    provider = resolve_provider(provider_name)
    runner = GraphRunner(
        provider=provider,
        checkpoint_store=checkpoint_store,
        decision_log=decision_log,
    )
    run = runner.run(graph, input_text=input_text)

    if run.status != expect_status:
        return False, f"status={run.status}, expected {expect_status}"
    return True, f"status={run.status}"
