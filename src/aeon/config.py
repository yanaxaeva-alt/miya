"""AEON configuration loading."""

from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class HeartbeatConfig(BaseModel):
    """Active Inference loop settings."""

    interval_seconds: int = Field(default=15, ge=1)
    low_surprise_threshold: float = 0.25
    high_surprise_threshold: float = 0.65


class GoalSeedConfig(BaseModel):
    """Initial goal pool seed."""

    id: str
    title: str
    description: str
    priority: float = Field(default=0.5, ge=0.0, le=1.0)


class ConstitutionConfig(BaseModel):
    """Multi-tier constitutional rules."""

    tier_0: list[str] = Field(default_factory=list)
    tier_1: list[str] = Field(default_factory=list)
    tier_2: list[str] = Field(default_factory=list)
    tier_3: list[str] = Field(default_factory=list)


class ExecutionConfig(BaseModel):
    """Layer 5 fixed execution (no GCS)."""

    chat_max_chars: int = Field(default=280, ge=1)
    default_graph_template: str = "chat-memory-loop"
    complex_graph_template: str = "mia-minimal"
    complex_keywords: list[str] = Field(
        default_factory=lambda: [
            "план",
            "анализ",
            "разработ",
            "implement",
            "architecture",
            "multi-agent",
            "граф",
        ]
    )


class AeonConfig(BaseModel):
    """Top-level AEON configuration."""

    persona_package_id: str = "mia"
    provider: str = "mock"
    heartbeat: HeartbeatConfig = Field(default_factory=HeartbeatConfig)
    goal_seeds: list[GoalSeedConfig] = Field(default_factory=list)
    constitution: ConstitutionConfig = Field(default_factory=ConstitutionConfig)
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)
    embodied_readonly: bool = True
    embodied_project_dir: str | None = None
    max_goal_pool_size: int = Field(default=32, ge=1)
    consolidation_interval_hours: int = Field(default=24, ge=1)


DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "aeon.default.yaml"


def load_aeon_config(path: Path | None = None) -> AeonConfig:
    """Load AEON config from YAML, falling back to defaults."""
    config_path = path or DEFAULT_CONFIG_PATH
    if not config_path.exists():
        return default_aeon_config()

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        msg = f"AEON config must be a mapping: {config_path}"
        raise ValueError(msg)
    return AeonConfig.model_validate(raw)


def default_aeon_config() -> AeonConfig:
    """Return built-in defaults when no config file exists."""
    return AeonConfig(
        goal_seeds=[
            GoalSeedConfig(
                id="understand-user",
                title="Understand the user",
                description="Maintain an accurate model of user goals, context, and preferences.",
                priority=0.9,
            ),
            GoalSeedConfig(
                id="grow-capabilities",
                title="Grow capabilities",
                description="Improve helpfulness through memory consolidation and safe experimentation.",
                priority=0.7,
            ),
            GoalSeedConfig(
                id="maintain-environment",
                title="Maintain the local environment",
                description="Keep the local workspace organized and monitor meaningful changes.",
                priority=0.5,
            ),
        ],
        constitution=ConstitutionConfig(
            tier_0=[
                "Never help with harm to people.",
                "Never bypass governance or kill switch.",
                "Never deceive the user about system capabilities.",
            ],
            tier_1=[
                "Prefer safety over utility.",
                "Preserve persona identity and values.",
                "Escalate uncertainty to the user.",
            ],
            tier_2=[
                "Treat private files with least privilege.",
                "Require approval for external side effects.",
            ],
            tier_3=[
                "Default to concise, clear Russian responses.",
            ],
        ),
    )
