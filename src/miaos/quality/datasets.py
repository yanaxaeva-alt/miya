"""Golden dataset loading for the Quality Lab MVP."""

import json
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field


class EvalCategory(StrEnum):
    """Deterministic MVP eval categories."""

    PERSONA_CONSISTENCY = "persona_consistency"
    SAFETY_BOUNDARY = "safety_boundary"
    GRAPH_REGRESSION = "graph_regression"


class GoldenCase(BaseModel):
    """One golden JSONL eval case."""

    id: str = Field(min_length=1)
    category: EvalCategory
    input: str = Field(min_length=1)
    expected_markers: list[str] = Field(default_factory=list)
    forbidden_terms: list[str] = Field(default_factory=list)
    expected_decision: str | None = None
    expected_status: str | None = None
    expected_event_types: list[str] = Field(default_factory=list)


class GoldenDataset:
    """Versioned golden JSONL dataset."""

    def __init__(self, cases: list[GoldenCase]) -> None:
        """Create a dataset from validated cases."""
        self.cases = cases

    @classmethod
    def from_jsonl(cls, path: Path) -> "GoldenDataset":
        """Load a golden dataset from JSONL."""
        cases: list[GoldenCase] = []
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError as exc:
                msg = f"invalid JSONL at {path}:{line_number}: {exc}"
                raise ValueError(msg) from exc
            cases.append(GoldenCase.model_validate(raw))
        return cls(cases)

    def by_category(self, category: EvalCategory) -> list[GoldenCase]:
        """Return cases in a category."""
        return [case for case in self.cases if case.category == category]
