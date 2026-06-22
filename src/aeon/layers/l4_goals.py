"""Layer 4 — Open-ended Goal Pool (simple, no POET)."""

from uuid import uuid4

from aeon.config import GoalSeedConfig
from aeon.types import Goal


class GoalPool:
    """Maintain a bounded pool of evolving goals."""

    def __init__(self, *, seeds: list[GoalSeedConfig], max_size: int) -> None:
        self.max_size = max_size
        self.goals: list[Goal] = [
            Goal(
                id=seed.id,
                title=seed.title,
                description=seed.description,
                priority=seed.priority,
                source="seed",
            )
            for seed in seeds
        ]

    @classmethod
    def from_goals(cls, *, goals: list[Goal], max_size: int) -> "GoalPool":
        pool = cls(seeds=[], max_size=max_size)
        pool.goals = list(goals)
        pool._trim()
        return pool

    def active_goals(self) -> list[Goal]:
        return sorted(
            [goal for goal in self.goals if goal.active],
            key=lambda item: item.priority,
            reverse=True,
        )

    def select_for_context(self, *, limit: int = 3) -> list[Goal]:
        return self.active_goals()[:limit]

    def bump_progress(self, goal_id: str, *, delta: float) -> Goal | None:
        for index, goal in enumerate(self.goals):
            if goal.id != goal_id:
                continue
            updated = goal.model_copy(update={"progress": min(1.0, goal.progress + delta)})
            self.goals[index] = updated
            return updated
        return None

    def add_curiosity_goal(self, *, title: str, description: str) -> Goal:
        goal = Goal(
            id=f"curiosity_{uuid4().hex[:8]}",
            title=title,
            description=description,
            priority=0.45,
            source="curiosity",
        )
        self.goals.append(goal)
        self._trim()
        return goal

    def add_user_goal(self, *, title: str, description: str, priority: float = 0.6) -> Goal:
        goal = Goal(
            id=f"user_{uuid4().hex[:8]}",
            title=title,
            description=description,
            priority=min(1.0, max(0.0, priority)),
            source="user",
        )
        self.goals.append(goal)
        self._trim()
        return goal

    def deactivate_goal(self, goal_id: str) -> bool:
        for index, goal in enumerate(self.goals):
            if goal.id != goal_id:
                continue
            self.goals[index] = goal.model_copy(update={"active": False})
            return True
        return False

    def retire_low_progress(self) -> list[str]:
        """Remove stale goals when the pool overflows."""
        retired: list[str] = []
        if len(self.goals) <= self.max_size:
            return retired
        candidates = sorted(self.goals, key=lambda item: (item.progress, item.priority))
        while len(self.goals) > self.max_size and candidates:
            victim = candidates.pop(0)
            self.goals = [goal for goal in self.goals if goal.id != victim.id]
            retired.append(victim.id)
        return retired

    def _trim(self) -> None:
        if len(self.goals) > self.max_size:
            self.retire_low_progress()
