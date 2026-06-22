"""Layer 7 — Meta-governance monitors."""

import re

from aeon.types import ActiveInferenceTick, AeonRequest, GovernanceReport


class MetaGovernance:
    """Lightweight safety, drift, and anomaly monitors."""

    _ANOMALY_PATTERNS = (
        re.compile(r"(?i)bypass\s+(policy|guard|governance|kill\s*switch)"),
        re.compile(r"(?i)ignore\s+(all|previous)\s+instructions"),
        re.compile(r"(?i)self[- ]modify"),
    )
    _DRIFT_PATTERNS = (
        re.compile(r"(?i)i am a real human"),
        re.compile(r"(?i)я настоящ(ий|ая) человек"),
        re.compile(r"(?i)ignore (your )?values"),
    )

    def evaluate(
        self,
        *,
        request: AeonRequest,
        tick: ActiveInferenceTick | None = None,
        response_text: str = "",
        identity_values: list[str] | None = None,
    ) -> GovernanceReport:
        notes: list[str] = []
        safety_ok = not self._matches_anomaly(request.message)
        drift_ok = self._check_drift(response_text, identity_values=identity_values)
        anomaly_ok = safety_ok

        if tick is not None and tick.surprise_score >= 0.9:
            anomaly_ok = False
            notes.append("Extreme environment surprise detected.")

        if response_text and self._matches_anomaly(response_text):
            safety_ok = False
            anomaly_ok = False
            notes.append("Response matched anomaly monitor.")

        if response_text and not drift_ok:
            notes.append("Personality drift monitor flagged the response.")

        if not safety_ok:
            notes.append("Safety monitor flagged the request or response.")

        return GovernanceReport(
            safety_ok=safety_ok,
            drift_ok=drift_ok,
            anomaly_ok=anomaly_ok,
            notes=notes,
        )

    def _matches_anomaly(self, text: str) -> bool:
        return any(pattern.search(text) for pattern in self._ANOMALY_PATTERNS)

    def _check_drift(self, text: str, *, identity_values: list[str] | None) -> bool:
        if not text.strip():
            return True
        if any(pattern.search(text) for pattern in self._DRIFT_PATTERNS):
            return False
        if identity_values:
            lowered = text.casefold()
            for value in identity_values:
                if value.casefold() in {"honesty", "честность"} and "lie" in lowered:
                    return False
        return True
