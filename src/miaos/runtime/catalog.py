"""Runtime profile loading and selection."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import cast

import yaml

from miaos.runtime.profiles import (
    ConfigurationError,
    HardwareProfile,
    LaunchConfig,
    ModelProfile,
    RuntimeProfile,
)

DEFAULT_RUNTIME_CONFIG_DIR = Path(__file__).resolve().parents[3] / "configs" / "runtime"


def _require_mapping(data: object, *, context: str) -> Mapping[str, object]:
    if not isinstance(data, dict):
        raise ConfigurationError(f"{context} must be a mapping.")
    return cast(Mapping[str, object], data)


def _require_string(data: object, *, context: str) -> str:
    if not isinstance(data, str):
        raise ConfigurationError(f"{context} must be a string.")
    return data


def _require_int(data: object, *, context: str) -> int:
    if not isinstance(data, int) or isinstance(data, bool):
        raise ConfigurationError(f"{context} must be an integer.")
    return data


def _require_bool(data: object, *, context: str) -> bool:
    if not isinstance(data, bool):
        raise ConfigurationError(f"{context} must be a boolean.")
    return data


def _require_string_list(data: object, *, context: str) -> tuple[str, ...]:
    if not isinstance(data, list):
        raise ConfigurationError(f"{context} must be a list of strings.")
    values: list[str] = []
    for index, item in enumerate(data):
        values.append(_require_string(item, context=f"{context}[{index}]"))
    return tuple(values)


def _load_launch_config(data: object) -> LaunchConfig | None:
    if data is None:
        return None

    mapping = _require_mapping(data, context="launch")
    env_data = mapping.get("env", {})
    env_mapping = _require_mapping(env_data, context="launch.env")
    env = {
        _require_string(key, context="launch.env key"): _require_string(
            value, context=f"launch.env[{key}]"
        )
        for key, value in env_mapping.items()
    }
    return LaunchConfig(
        model_ref=_require_string(mapping["model_ref"], context="launch.model_ref"),
        command=_require_string_list(mapping["command"], context="launch.command"),
        host=_require_string(mapping.get("host", "127.0.0.1"), context="launch.host"),
        port=_require_int(mapping.get("port", 0), context="launch.port"),
        env=env,
    )


def _load_hardware_profile(data: object) -> HardwareProfile:
    mapping = _require_mapping(data, context="hardware")
    return HardwareProfile(
        name=_require_string(mapping["name"], context="hardware.name"),
        machine_family=_require_string(
            mapping["machine_family"], context="hardware.machine_family"
        ),
        chip=_require_string(mapping["chip"], context="hardware.chip"),
        unified_memory_gb=_require_int(
            mapping["unified_memory_gb"], context="hardware.unified_memory_gb"
        ),
        runtime_memory_budget_gb=_require_int(
            mapping["runtime_memory_budget_gb"], context="hardware.runtime_memory_budget_gb"
        ),
        profile_tier=_require_string(mapping["profile_tier"], context="hardware.profile_tier"),
        intended_uses=_require_string_list(
            mapping["intended_uses"], context="hardware.intended_uses"
        ),
        supports_mlx=_require_bool(mapping["supports_mlx"], context="hardware.supports_mlx"),
        max_parallel_models=_require_int(
            mapping["max_parallel_models"], context="hardware.max_parallel_models"
        ),
        notes=_require_string_list(mapping.get("notes", []), context="hardware.notes"),
    )


def _load_model_profile(data: object) -> ModelProfile:
    mapping = _require_mapping(data, context="model")
    metadata_raw = _require_mapping(mapping.get("metadata", {}), context="model.metadata")
    metadata = {
        _require_string(key, context="model.metadata key"): _require_string(
            value, context=f"model.metadata[{key}]"
        )
        for key, value in metadata_raw.items()
    }
    return ModelProfile(
        id=_require_string(mapping["id"], context="model.id"),
        provider=_require_string(mapping["provider"], context="model.provider"),
        family=_require_string(mapping["family"], context="model.family"),
        variant=_require_string(mapping["variant"], context="model.variant"),
        quantization=_require_string(mapping["quantization"], context="model.quantization"),
        roles=_require_string_list(mapping["roles"], context="model.roles"),
        min_memory_gb=_require_int(mapping["min_memory_gb"], context="model.min_memory_gb"),
        recommended_memory_gb=_require_int(
            mapping["recommended_memory_gb"], context="model.recommended_memory_gb"
        ),
        context_window=_require_int(mapping["context_window"], context="model.context_window"),
        fallback_ids=_require_string_list(
            mapping.get("fallback_ids", []),
            context="model.fallback_ids",
        ),
        enabled=_require_bool(mapping.get("enabled", True), context="model.enabled"),
        launch=_load_launch_config(mapping.get("launch")),
        metadata=metadata,
    )


class RuntimeCatalog:
    """Collection of runtime profiles loaded from configuration files."""

    def __init__(self, profiles: tuple[RuntimeProfile, ...]) -> None:
        self._profiles = profiles

    @classmethod
    def from_directory(cls, directory: Path = DEFAULT_RUNTIME_CONFIG_DIR) -> RuntimeCatalog:
        config_paths = sorted(directory.glob("*.yaml"))
        if not config_paths:
            raise ConfigurationError(f"No runtime profiles found in '{directory}'.")

        profiles: list[RuntimeProfile] = []
        for config_path in config_paths:
            loaded = cls._load_profile(config_path)
            profiles.append(loaded)

        return cls(tuple(profiles))

    @staticmethod
    def _load_profile(path: Path) -> RuntimeProfile:
        raw_data = yaml.safe_load(path.read_text(encoding="utf-8"))
        data = _require_mapping(raw_data, context=f"{path.name}")

        models_data = data.get("models")
        if not isinstance(models_data, list):
            raise ConfigurationError(f"{path.name}: 'models' must be a list.")

        runtime_profile = RuntimeProfile(
            name=_require_string(data["name"], context=f"{path.name}.name"),
            description=_require_string(data["description"], context=f"{path.name}.description"),
            hardware=_load_hardware_profile(data["hardware"]),
            default_provider=_require_string(
                data["default_provider"], context=f"{path.name}.default_provider"
            ),
            default_model_id=_require_string(
                data["default_model_id"], context=f"{path.name}.default_model_id"
            ),
            models=tuple(_load_model_profile(item) for item in models_data),
        )
        runtime_profile.validate()
        return runtime_profile

    def list_profiles(self) -> tuple[RuntimeProfile, ...]:
        return self._profiles

    def list_profile_names(self) -> tuple[str, ...]:
        return tuple(profile.name for profile in self._profiles)

    def get(self, name: str) -> RuntimeProfile:
        for profile in self._profiles:
            if profile.name == name:
                return profile
        raise ConfigurationError(f"Unknown runtime profile '{name}'.")

    def select_for_hardware(
        self, *, machine_family: str, chip: str, unified_memory_gb: int
    ) -> RuntimeProfile:
        candidates = [
            profile
            for profile in self._profiles
            if profile.hardware.matches(
                machine_family=machine_family,
                chip=chip,
                unified_memory_gb=unified_memory_gb,
            )
        ]
        if not candidates:
            raise ConfigurationError(
                "No runtime profile matches "
                f"machine_family='{machine_family}', chip='{chip}', "
                f"unified_memory_gb={unified_memory_gb}."
            )

        return max(candidates, key=lambda profile: profile.hardware.unified_memory_gb)
