"""Layer 3 — Active Inference Loop."""

from uuid import uuid4

from aeon.config import HeartbeatConfig
from aeon.layers.l1_embodied import EmbodiedInterface
from aeon.types import ActiveInferenceTick, SurpriseLevel, WorldSnapshot


class ActiveInferenceLoop:
    """Heuristic surprise-driven heartbeat without a full JEPA world model."""

    def __init__(
        self,
        *,
        embodied: EmbodiedInterface,
        config: HeartbeatConfig,
    ) -> None:
        self.embodied = embodied
        self.config = config
        self._last_snapshot: WorldSnapshot | None = None

    def tick(self) -> ActiveInferenceTick:
        """Run one perception-predict-compare-act cycle."""
        snapshot = self.embodied.snapshot()
        predicted = self._predict(snapshot)
        score = self._surprise_score(previous=self._last_snapshot, current=snapshot)
        surprise = self._band(score)
        action = self._select_action(surprise)
        self._last_snapshot = snapshot
        return ActiveInferenceTick(
            tick_id=f"tick_{uuid4().hex[:12]}",
            snapshot=snapshot,
            predicted_summary=predicted,
            surprise=surprise,
            surprise_score=score,
            selected_action=action,
        )

    def _predict(self, snapshot: WorldSnapshot) -> str:
        if self._last_snapshot is None:
            return "Initial baseline: no prior world state."
        return (
            f"Expect cwd={self._last_snapshot.cwd} with "
            f"{len(self._last_snapshot.recent_files)} tracked files unchanged."
        )

    @staticmethod
    def _surprise_score(*, previous: WorldSnapshot | None, current: WorldSnapshot) -> float:
        if previous is None:
            return 0.1
        previous_files = set(previous.recent_files)
        current_files = set(current.recent_files)
        file_delta = len(previous_files.symmetric_difference(current_files))
        cwd_changed = 0.4 if previous.cwd != current.cwd else 0.0
        return min(1.0, cwd_changed + file_delta * 0.08)

    def _band(self, score: float) -> SurpriseLevel:
        if score >= self.config.high_surprise_threshold:
            return SurpriseLevel.HIGH
        if score >= self.config.low_surprise_threshold:
            return SurpriseLevel.MEDIUM
        return SurpriseLevel.LOW

    @staticmethod
    def _select_action(surprise: SurpriseLevel) -> str:
        if surprise == SurpriseLevel.LOW:
            return "routine_monitor"
        if surprise == SurpriseLevel.MEDIUM:
            return "local_plan"
        return "escalate_to_governance"
