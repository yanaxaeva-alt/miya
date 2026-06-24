"""AEON runtime orchestrator without GCS."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from miaos.executor import CheckpointStore
from miaos.memory import MemoryStore
from miaos.observability import DecisionLog, new_trace_id
from miaos.persona import create_persona_package

from aeon.config import AeonConfig, load_aeon_config
from aeon.consolidation import ConsolidationSummary
from aeon.layers.l1_embodied import EmbodiedInterface
from aeon.layers.l2_memory import SubstrateMemory
from aeon.layers.l3_active_inference import ActiveInferenceLoop
from aeon.layers.l4_goals import GoalPool
from aeon.layers.l5_execution import FixedExecutionLayer
from aeon.layers.l6_identity import IdentityCore
from aeon.layers.l7_governance import MetaGovernance
from aeon.layers.l8_constitution import ConstitutionalCore
from aeon.persistence.goals_store import goals_path, load_goals, save_goals
from aeon.persistence.tick_store import append_tick, load_recent_ticks, ticks_path
from aeon.types import (
    ActiveInferenceTick,
    AeonRequest,
    AeonResponse,
    ConstitutionalVerdict,
    ExecutionMode,
    Goal,
    GovernanceReport,
    SurpriseLevel,
)

if TYPE_CHECKING:
    from miaos.safety.approval_queue import ApprovalQueue

REASONING_MARKERS = (
    "Thinking Process:",
    "Thinking process:",
    "Reasoning:",
    "Chain of thought:",
    "Thought process:",
    "AEON memory context",
    "provided context",
)
FINAL_ANSWER_MARKERS = (
    "Final Answer:",
    "Final answer:",
    "Answer:",
    "Ответ:",
)


class AeonRuntime:
    """Wire AEON layers 1-4 and 6-8; Layer 5 uses fixed MiaOS execution."""

    def __init__(
        self,
        *,
        base_dir: Path,
        config: AeonConfig | None = None,
        approval_queue: ApprovalQueue | None = None,
    ) -> None:
        self.base_dir = base_dir
        self.config = config or load_aeon_config()
        self.approval_queue = approval_queue
        self.base_dir.mkdir(parents=True, exist_ok=True)

        self.decision_log = DecisionLog(self.base_dir / "decisions.jsonl")
        self.checkpoint_store = CheckpointStore(self.base_dir / "checkpoints.sqlite3")
        memory_store = MemoryStore(SubstrateMemory.default_db_path(self.base_dir))
        self.memory = SubstrateMemory(memory_store, package_id=self.config.persona_package_id)

        extra_dirs = self._resolve_extra_watch_dirs()
        self.embodied = EmbodiedInterface(
            readonly=self.config.embodied_readonly,
            watch_dir=self.base_dir,
            extra_watch_dirs=extra_dirs,
        )
        self.active_inference = ActiveInferenceLoop(
            embodied=self.embodied,
            config=self.config.heartbeat,
        )
        self._goals_path = goals_path(self.base_dir)
        self._ticks_path = ticks_path(self.base_dir)
        self.goals = self._load_goal_pool()
        self.identity = self._load_identity()
        self.constitution = ConstitutionalCore(self.config.constitution)
        self.governance = MetaGovernance()
        self.execution = FixedExecutionLayer(
            identity=self.identity,
            provider_name=self.config.provider,
            decision_log=self.decision_log,
            checkpoint_store=self.checkpoint_store,
            config=self.config.execution,
        )

    def tick(self) -> dict[str, object]:
        """Run one always-on heartbeat cycle."""
        tick = self.active_inference.tick()
        governance = self.governance.evaluate(request=AeonRequest(message="heartbeat"), tick=tick)
        action_effects = self._execute_heartbeat_action(tick, governance)

        result: dict[str, object] = {
            "tick_id": tick.tick_id,
            "surprise": tick.surprise.value,
            "surprise_score": tick.surprise_score,
            "action": tick.selected_action,
            "governance_ok": governance.anomaly_ok and governance.safety_ok,
            **action_effects,
        }
        append_tick(self._ticks_path, result)
        return result

    def ask(self, request: AeonRequest) -> AeonResponse:
        """Handle one user request through constitutional, governance, and execution layers."""
        trace_id = request.trace_id or new_trace_id()
        request = request.model_copy(update={"trace_id": trace_id})

        pre_verdict = self.constitution.ratify_request(request)
        if not pre_verdict.allowed:
            governance = self.governance.evaluate(
                request=request,
                identity_values=self.identity.values,
            )
            return AeonResponse(
                trace_id=trace_id,
                text=f"Constitutional Core blocked the request: {pre_verdict.reason}",
                execution_mode=ExecutionMode.CHAT,
                blocked=True,
                constitutional=pre_verdict,
                governance=governance,
            )

        if pre_verdict.requires_human:
            return self._approval_blocked_response(
                trace_id=trace_id,
                request=request,
                constitutional=pre_verdict,
                reason="Request requires human approval before execution (Tier 2).",
            )

        tick = self.active_inference.tick()
        governance = self.governance.evaluate(
            request=request,
            tick=tick,
            identity_values=self.identity.values,
        )
        if not governance.safety_ok or not governance.anomaly_ok:
            return AeonResponse(
                trace_id=trace_id,
                text="Meta-governance blocked the request before execution.",
                execution_mode=ExecutionMode.CHAT,
                blocked=True,
                constitutional=pre_verdict,
                governance=governance,
            )

        active_goals = self.goals.select_for_context()
        memory_context = self._build_memory_context(active_goals)
        text, mode, graph_id = self.execution.execute(request, memory_context=memory_context)
        text = public_response_text(text)

        post_governance = self.governance.evaluate(
            request=request,
            response_text=text,
            identity_values=self.identity.values,
        )
        if not post_governance.safety_ok or not post_governance.drift_ok:
            return AeonResponse(
                trace_id=trace_id,
                text="Meta-governance blocked the generated response.",
                execution_mode=mode,
                graph_id=graph_id,
                blocked=True,
                constitutional=pre_verdict,
                governance=post_governance,
            )

        post_verdict = self.constitution.ratify_response(text)
        if not post_verdict.allowed:
            return AeonResponse(
                trace_id=trace_id,
                text="Constitutional Core blocked the generated response.",
                execution_mode=mode,
                graph_id=graph_id,
                blocked=True,
                constitutional=post_verdict,
                governance=post_governance,
            )

        primary_goal = active_goals[0] if active_goals else None
        if primary_goal is not None:
            self.goals.bump_progress(primary_goal.id, delta=self._progress_delta(request.message))
            self._persist_goals()

        self.memory.remember_episode(
            trace_id=trace_id,
            role="user",
            content=request.message,
            tags=["aeon", "request"],
        )
        self.memory.remember_episode(
            trace_id=trace_id,
            role="assistant",
            content=text,
            tags=["aeon", "response", mode.value],
        )

        return AeonResponse(
            trace_id=trace_id,
            text=text,
            execution_mode=mode,
            graph_id=graph_id,
            constitutional=post_verdict,
            governance=post_governance,
            goal_id=primary_goal.id if primary_goal else None,
            metadata={
                "requires_human": pre_verdict.requires_human,
                "surprise": tick.surprise.value,
            },
        )

    def status(self) -> dict[str, object]:
        """Return a compact runtime status snapshot."""
        return {
            "identity": self.identity.name,
            "values": self.identity.values,
            "provider": self.config.provider,
            "heartbeat_interval_seconds": self.config.heartbeat.interval_seconds,
            "consolidation_interval_hours": self.config.consolidation_interval_hours,
            "active_goals": [goal.model_dump() for goal in self.goals.active_goals()],
            "recent_episodes": self.memory.recent_episodes(limit=3),
            "skill_hints": self.memory.skill_hints(limit=3),
            "recent_ticks": load_recent_ticks(self._ticks_path, limit=5),
            "watch_dirs": [str(self.embodied.watch_dir)] + [str(path) for path in self.embodied.extra_watch_dirs],
        }

    def add_goal(self, *, title: str, description: str, priority: float = 0.6) -> Goal:
        goal = self.goals.add_user_goal(title=title, description=description, priority=priority)
        self._persist_goals()
        return goal

    def deactivate_goal(self, goal_id: str) -> bool:
        changed = self.goals.deactivate_goal(goal_id)
        if changed:
            self._persist_goals()
        return changed

    def consolidate(self) -> dict[str, object]:
        """Morning-style consolidation: groom goals and distill recent episodes."""
        episodes = self.memory.recent_episodes(limit=20)
        retired = self.goals.retire_low_progress()
        self._apply_episode_progress(episodes)
        self._persist_goals()
        summary = ConsolidationSummary.from_episodes(episodes, retired_goal_ids=retired)
        skill_name = "morning_consolidation"
        if episodes:
            self.memory.remember_skill(name=skill_name, content=summary.to_note())
        return {
            "retired_goal_ids": retired,
            "active_goal_count": len(self.goals.active_goals()),
            "episodes_seen": len(episodes),
            "skill_recorded": bool(episodes),
            "summary": summary.to_note(),
        }

    def _execute_heartbeat_action(
        self,
        tick: ActiveInferenceTick,
        governance: GovernanceReport,
    ) -> dict[str, object]:
        effects: dict[str, object] = {}
        snapshot = tick.snapshot

        if tick.selected_action == "escalate_to_governance":
            if not governance.anomaly_ok:
                self.memory.remember_episode(
                    trace_id=tick.tick_id,
                    role="system",
                    content=f"Heartbeat escalated: surprise={tick.surprise_score:.2f}",
                    tags=["heartbeat", "governance"],
                )
            if tick.surprise == SurpriseLevel.HIGH:
                goal = self.goals.add_curiosity_goal(
                    title="Investigate environment change",
                    description=(
                        f"Surprise={tick.surprise_score:.2f} in {snapshot.cwd}; "
                        f"files={len(snapshot.recent_files)}"
                    ),
                )
                self._persist_goals()
                effects["curiosity_goal_id"] = goal.id
            return effects

        if tick.selected_action == "local_plan":
            plan = (
                f"Local plan after medium surprise ({tick.surprise_score:.2f}): "
                f"review {len(snapshot.recent_files)} tracked files in {snapshot.cwd}."
            )
            self.memory.remember_skill(name="local_plan", content=plan)
            self.memory.remember_episode(
                trace_id=tick.tick_id,
                role="system",
                content=plan,
                tags=["heartbeat", "plan"],
            )
            effects["plan_recorded"] = True
            return effects

        monitor_note = (
            f"Routine monitor: {len(snapshot.recent_files)} files tracked under {snapshot.cwd}."
        )
        self.memory.remember_episode(
            trace_id=tick.tick_id,
            role="system",
            content=monitor_note,
            tags=["heartbeat", "monitor"],
        )
        effects["monitor_recorded"] = True
        return effects

    def _approval_blocked_response(
        self,
        *,
        trace_id: str,
        request: AeonRequest,
        constitutional: ConstitutionalVerdict,
        reason: str,
    ) -> AeonResponse:
        governance = self.governance.evaluate(
            request=request,
            identity_values=self.identity.values,
        )
        metadata: dict[str, object] = {"requires_human": True}
        text = reason
        if self.approval_queue is not None:
            approval = self.approval_queue.enqueue_aeon_side_effect(
                trace_id=trace_id,
                message=request.message,
                summary=f"AEON Tier 2 checkpoint: {request.message[:160]}",
                provider=self.config.provider,
            )
            metadata["approval_request_id"] = approval.request_id
            text = f"{reason} Approval queued: {approval.request_id}"
        return AeonResponse(
            trace_id=trace_id,
            text=text,
            execution_mode=ExecutionMode.CHAT,
            blocked=True,
            constitutional=constitutional,
            governance=governance,
            metadata=metadata,
        )

    @staticmethod
    def _progress_delta(message: str) -> float:
        if len(message) > 120:
            return 0.08
        return 0.05

    def _apply_episode_progress(self, episodes: list[str]) -> None:
        joined = "\n".join(episodes).casefold()
        for goal in self.goals.active_goals():
            if goal.title.casefold() in joined or goal.id in joined:
                self.goals.bump_progress(goal.id, delta=0.1)

    def _resolve_extra_watch_dirs(self) -> list[Path]:
        candidates: list[Path] = []
        project_dir = self.config.embodied_project_dir or os.environ.get("MIYA_PROJECT_DIR")
        if project_dir:
            path = Path(project_dir)
            if path.exists():
                candidates.append(path)
        return candidates

    def _load_goal_pool(self) -> GoalPool:
        if self._goals_path.exists():
            stored = load_goals(self._goals_path)
            if stored:
                return GoalPool.from_goals(goals=stored, max_size=self.config.max_goal_pool_size)
        pool = GoalPool(seeds=self.config.goal_seeds, max_size=self.config.max_goal_pool_size)
        save_goals(self._goals_path, pool.goals)
        return pool

    def _persist_goals(self) -> None:
        save_goals(self._goals_path, self.goals.goals)

    def _build_memory_context(self, goals: list[Goal]) -> str:
        episodes = self.memory.recent_episodes(limit=3)
        skills = self.memory.skill_hints(limit=3)
        goal_lines = [f"- {goal.title}: {goal.description}" for goal in goals]
        chunks = []
        if goal_lines:
            chunks.append("Active goals:\n" + "\n".join(goal_lines))
        if episodes:
            chunks.append("Recent episodes:\n" + "\n".join(episodes))
        if skills:
            chunks.append("Skill hints:\n" + "\n".join(skills))
        return "\n\n".join(chunks)

    def _load_identity(self) -> IdentityCore:
        persona_dir = self.base_dir / "personas" / self.config.persona_package_id
        if persona_dir.exists():
            return IdentityCore.from_directory(persona_dir)

        example_profile = Path(__file__).resolve().parents[2] / "examples" / "mia-minimal" / "persona.yaml"
        create_persona_package(
            name="Mia",
            profile_path=example_profile,
            output_path=persona_dir,
        )
        return IdentityCore.from_directory(persona_dir)


def public_response_text(text: str) -> str:
    """Return a user-facing response with hidden reasoning markers removed."""
    stripped = text.strip()
    if not stripped:
        return stripped

    marker_index = _first_marker_index(stripped, REASONING_MARKERS)
    has_markdown_artifact = stripped.startswith(("**", "* Based on"))
    if marker_index is None and not has_markdown_artifact:
        return stripped

    if marker_index is not None:
        final = _extract_after_marker(stripped, FINAL_ANSWER_MARKERS)
        if final:
            return final

        prefix = stripped[:marker_index].strip()
        if prefix and not prefix.startswith(("**", "*")):
            return prefix

    return (
        "Сейчас запрос проходит проверку правил, получает контекст целей "
        "и памяти и передается в исполнительный слой."
    )


def _first_marker_index(text: str, markers: tuple[str, ...]) -> int | None:
    indexes = [index for marker in markers if (index := text.find(marker)) >= 0]
    return min(indexes) if indexes else None


def _extract_after_marker(text: str, markers: tuple[str, ...]) -> str:
    for marker in markers:
        if marker in text:
            return text.split(marker, maxsplit=1)[1].strip()
    return ""
