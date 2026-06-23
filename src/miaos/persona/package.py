"""Directory-based `.mia` package create, load, and validation helpers."""

import io
import json
import shutil
import tempfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel

from miaos.persona.schemas import (
    AutonomyContractRef,
    ModelBinding,
    PersonaCard,
    PersonaIdentity,
    PersonaManifest,
)


class PersonaPackageError(RuntimeError):
    """Raised when a `.mia` package cannot be created or validated."""


class PersonaPackage(BaseModel):
    """Loaded minimal `.mia` package."""

    root: Path
    manifest: PersonaManifest
    card: PersonaCard
    model_binding: ModelBinding
    autonomy_contract_ref: AutonomyContractRef


def create_persona_package(
    *,
    name: str,
    profile_path: Path,
    output_path: Path | None = None,
) -> PersonaPackage:
    """Create a minimal directory-based `.mia` package."""
    profile = _load_yaml_mapping(profile_path)
    root = output_path or profile_path.parent
    root.mkdir(parents=True, exist_ok=True)

    card = _card_from_profile(name=name, profile=profile)
    model_binding = _model_binding_from_profile(profile)
    autonomy_ref = _autonomy_ref_from_profile(profile)
    manifest = PersonaManifest(persona_id=card.identity.id, name=card.identity.name)

    _write_json(root / manifest.identity_path, card.identity)
    _write_json(root / manifest.values_path, {"ranked": card.values})
    _write_json(root / manifest.model_binding_path, model_binding)
    _write_json(root / manifest.autonomy_contract_ref_path, autonomy_ref)
    _write_json(root / "manifest.json", manifest)

    # TODO(block=16, sprint=5): add Merkle tree and signature verification  # noqa: FIX002, TD003
    return PersonaPackage(
        root=root,
        manifest=manifest,
        card=card,
        model_binding=model_binding,
        autonomy_contract_ref=autonomy_ref,
    )


def load_persona_package(path: Path) -> PersonaPackage:
    """Load and validate a minimal `.mia` package."""
    manifest_path = path / "manifest.json"
    if not manifest_path.exists():
        msg = f"persona package manifest not found: {manifest_path}"
        raise PersonaPackageError(msg)

    manifest = PersonaManifest.model_validate(_read_json(manifest_path))
    identity = PersonaIdentity.model_validate(_read_json(path / manifest.identity_path))
    values_raw = _read_json(path / manifest.values_path)
    if not isinstance(values_raw.get("ranked"), list):
        msg = f"persona values file must contain ranked list: {manifest.values_path}"
        raise PersonaPackageError(msg)
    values = [str(value) for value in values_raw["ranked"]]
    card = PersonaCard(identity=identity, values=values)
    model_binding = ModelBinding.model_validate(_read_json(path / manifest.model_binding_path))
    autonomy_ref = AutonomyContractRef.model_validate(
        _read_json(path / manifest.autonomy_contract_ref_path)
    )
    return PersonaPackage(
        root=path,
        manifest=manifest,
        card=card,
        model_binding=model_binding,
        autonomy_contract_ref=autonomy_ref,
    )


def validate_persona_package(path: Path) -> PersonaManifest:
    """Validate a minimal `.mia` package and return its manifest."""
    return load_persona_package(path).manifest


def update_persona_model_binding(
    path: Path,
    *,
    provider: str,
    model_id: str,
) -> PersonaPackage:
    """Update one package model binding and return the reloaded package."""
    package = load_persona_package(path)
    binding = package.model_binding.model_copy(update={"provider": provider, "model_id": model_id})
    manifest = package.manifest.model_copy(update={"updated_at": datetime.now(UTC)})
    _write_json(path / package.manifest.model_binding_path, binding)
    _write_json(path / "manifest.json", manifest)
    return load_persona_package(path)


def export_persona_archive(path: Path) -> bytes:
    """Zip a validated persona package directory for portable export."""
    validate_persona_package(path)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for file_path in sorted(path.rglob("*")):
            if file_path.is_file():
                archive.write(file_path, arcname=file_path.relative_to(path).as_posix())
    return buffer.getvalue()


def import_persona_archive(
    data: bytes,
    persona_dir: Path,
    *,
    package_id: str | None = None,
    overwrite: bool = False,
) -> PersonaPackage:
    """Import a zipped persona package into the persona directory."""
    buffer = io.BytesIO(data)
    if not zipfile.is_zipfile(buffer):
        msg = "upload must be a .zip persona archive"
        raise PersonaPackageError(msg)

    buffer.seek(0)
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_root = Path(temp_dir)
        with zipfile.ZipFile(buffer) as archive:
            archive.extractall(temp_root)
        package_root = _find_package_root(temp_root)
        load_persona_package(package_root)
        target_id = package_id or package_root.name
        target_path = persona_dir / target_id
        if target_path.exists() and not overwrite:
            msg = f"persona package {target_id!r} already exists"
            raise PersonaPackageError(msg)
        if target_path.exists():
            shutil.rmtree(target_path)
        persona_dir.mkdir(parents=True, exist_ok=True)
        shutil.copytree(package_root, target_path)
        return load_persona_package(target_path)


def _find_package_root(extracted: Path) -> Path:
    """Locate manifest.json inside an extracted archive."""
    if (extracted / "manifest.json").exists():
        return extracted
    for child in sorted(extracted.iterdir()):
        if child.is_dir() and (child / "manifest.json").exists():
            return child
    msg = "persona archive must contain manifest.json at root"
    raise PersonaPackageError(msg)


def _load_yaml_mapping(path: Path) -> dict[str, Any]:
    """Load a YAML mapping from disk."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        msg = f"persona profile must be a YAML mapping: {path}"
        raise PersonaPackageError(msg)
    return raw


def _card_from_profile(*, name: str, profile: dict[str, Any]) -> PersonaCard:
    """Build a persona card from profile YAML data."""
    identity_raw = profile.get("identity", {})
    if not isinstance(identity_raw, dict):
        msg = "identity must be a mapping"
        raise PersonaPackageError(msg)

    identity = PersonaIdentity(
        name=name,
        role=str(identity_raw.get("role", "Virtual personality")),
        default_locale=str(identity_raw.get("default_locale", "ru-RU")),
        biography_seed=_optional_str(identity_raw.get("biography_seed")),
    )
    values_raw = profile.get("values", {})
    values = _values_from_raw(values_raw)
    return PersonaCard(identity=identity, values=values)


def _model_binding_from_profile(profile: dict[str, Any]) -> ModelBinding:
    """Build model binding from profile YAML data."""
    raw = profile.get("model_binding", {})
    if not isinstance(raw, dict):
        msg = "model_binding must be a mapping"
        raise PersonaPackageError(msg)
    return ModelBinding.model_validate(raw)


def _autonomy_ref_from_profile(profile: dict[str, Any]) -> AutonomyContractRef:
    """Build autonomy contract reference from profile YAML data."""
    raw = profile.get("autonomy_contract", {})
    if not isinstance(raw, dict):
        msg = "autonomy_contract must be a mapping"
        raise PersonaPackageError(msg)
    return AutonomyContractRef.model_validate(raw)


def _values_from_raw(raw: object) -> list[str]:
    """Normalize values from simple list or `{ranked: [...]}` mapping."""
    if isinstance(raw, list):
        return [str(value) for value in raw]
    if isinstance(raw, dict) and isinstance(raw.get("ranked"), list):
        return [str(value) for value in raw["ranked"]]
    return ["honesty", "care"]


def _optional_str(value: object) -> str | None:
    """Return optional string value."""
    if value is None:
        return None
    return str(value)


def _write_json(path: Path, payload: BaseModel | dict[str, list[str]]) -> None:
    """Write a JSON file, creating parents as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(payload, BaseModel):
        body = payload.model_dump_json(indent=2)
    else:
        body = json.dumps(payload, ensure_ascii=False, indent=2)
    path.write_text(f"{body}\n", encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    """Read a JSON mapping from disk."""
    if not path.exists():
        msg = f"persona package file not found: {path}"
        raise PersonaPackageError(msg)
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        msg = f"persona package file must contain a JSON object: {path}"
        raise PersonaPackageError(msg)
    return raw
