"""Morning-style consolidation helpers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ConsolidationSummary:
    """Structured distillation of recent AEON activity."""

    episode_count: int
    user_topics: list[str]
    assistant_topics: list[str]
    retired_goal_ids: list[str]

    def to_note(self) -> str:
        user_line = "; ".join(self.user_topics[:3]) or "none"
        assistant_line = "; ".join(self.assistant_topics[:3]) or "none"
        retired = ", ".join(self.retired_goal_ids) or "none"
        return (
            f"episodes={self.episode_count}; "
            f"user_topics={user_line[:240]}; "
            f"assistant_topics={assistant_line[:240]}; "
            f"retired_goals={retired}"
        )

    @classmethod
    def from_episodes(
        cls,
        episodes: list[str],
        *,
        retired_goal_ids: list[str],
    ) -> ConsolidationSummary:
        user_topics: list[str] = []
        assistant_topics: list[str] = []
        for episode in episodes:
            if episode.startswith("user:"):
                user_topics.append(episode.removeprefix("user:").strip()[:120])
            elif episode.startswith("assistant:"):
                assistant_topics.append(episode.removeprefix("assistant:").strip()[:120])
        return cls(
            episode_count=len(episodes),
            user_topics=user_topics,
            assistant_topics=assistant_topics,
            retired_goal_ids=retired_goal_ids,
        )
