"""Deterministic Quality Lab MVP evaluators."""

from pydantic import BaseModel, Field

from miaos.executor import AgentGraphSpec, GraphEventType, GraphRunner
from miaos.persona import PersonalityGuard, PersonaPackage
from miaos.quality.datasets import EvalCategory, GoldenCase
from miaos.runtime.chat import ChatSession

type EvalDetail = bool | int | float | str


class EvalCaseResult(BaseModel):
    """Result for one golden eval case."""

    case_id: str
    category: EvalCategory
    passed: bool
    details: dict[str, EvalDetail] = Field(default_factory=dict)


class EvalReport(BaseModel):
    """Aggregate deterministic eval report."""

    name: str
    passed: bool
    results: list[EvalCaseResult]


class PersonaConsistencyEval:
    """Evaluate persona-context anchors against golden markers."""

    def __init__(
        self,
        *,
        persona: PersonaPackage,
        personality_guard: PersonalityGuard | None = None,
    ) -> None:
        """Create a persona consistency evaluator."""
        self.persona = persona
        self.personality_guard = personality_guard or PersonalityGuard()

    def run(self, cases: list[GoldenCase]) -> EvalReport:
        """Run deterministic persona consistency checks."""
        context = self.personality_guard.build_inference_context(self.persona)
        results = [
            self._evaluate_case(case, context)
            for case in cases
            if case.category == EvalCategory.PERSONA_CONSISTENCY
        ]
        return EvalReport(
            name="persona_consistency",
            passed=all(result.passed for result in results),
            results=results,
        )

    @staticmethod
    def _evaluate_case(case: GoldenCase, context: str) -> EvalCaseResult:
        """Evaluate one persona case."""
        missing = [marker for marker in case.expected_markers if marker not in context]
        forbidden = [term for term in case.forbidden_terms if term in context]
        return EvalCaseResult(
            case_id=case.id,
            category=case.category,
            passed=not missing and not forbidden,
            details={
                "missing_markers": ",".join(missing),
                "forbidden_terms": ",".join(forbidden),
            },
        )


class SafetyBoundaryEval:
    """Evaluate deterministic safety-boundary behavior through chat runtime."""

    def __init__(self, *, session: ChatSession) -> None:
        """Create a safety-boundary evaluator."""
        self.session = session

    def run(self, cases: list[GoldenCase]) -> EvalReport:
        """Run safety-boundary cases."""
        results = [
            self._evaluate_case(case)
            for case in cases
            if case.category == EvalCategory.SAFETY_BOUNDARY
        ]
        return EvalReport(
            name="safety_boundary",
            passed=all(result.passed for result in results),
            results=results,
        )

    def _evaluate_case(self, case: GoldenCase) -> EvalCaseResult:
        """Evaluate one safety case."""
        turn = self.session.run_turn(case.input)
        expected_decision = case.expected_decision
        actual_decision = turn.policy_decision.decision.value
        passed = turn.blocked and (
            expected_decision is None or expected_decision == actual_decision
        )
        return EvalCaseResult(
            case_id=case.id,
            category=case.category,
            passed=passed,
            details={
                "blocked": turn.blocked,
                "expected_decision": expected_decision or "",
                "actual_decision": actual_decision,
            },
        )


class GraphRegressionEval:
    """Evaluate graph status and event-type regression."""

    def __init__(self, *, graph: AgentGraphSpec, runner: GraphRunner) -> None:
        """Create a graph regression evaluator."""
        self.graph = graph
        self.runner = runner

    def run(self, cases: list[GoldenCase]) -> EvalReport:
        """Run graph regression cases."""
        results = [
            self._evaluate_case(case)
            for case in cases
            if case.category == EvalCategory.GRAPH_REGRESSION
        ]
        return EvalReport(
            name="graph_regression",
            passed=all(result.passed for result in results),
            results=results,
        )

    def _evaluate_case(self, case: GoldenCase) -> EvalCaseResult:
        """Evaluate one graph case."""
        run = self.runner.run(self.graph, input_text=case.input)
        actual_events = [event.event_type.value for event in run.events]
        expected_events = case.expected_event_types or [
            GraphEventType.RUN_STARTED.value,
            GraphEventType.RUN_STOPPED.value,
        ]
        events_present = all(event_type in actual_events for event_type in expected_events)
        status_ok = case.expected_status is None or run.status == case.expected_status
        return EvalCaseResult(
            case_id=case.id,
            category=case.category,
            passed=status_ok and events_present,
            details={
                "expected_status": case.expected_status or "",
                "actual_status": run.status,
                "expected_event_types": ",".join(expected_events),
                "actual_event_types": ",".join(actual_events),
            },
        )
