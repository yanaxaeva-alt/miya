"""Tests for minimal `.mia` persona package handling."""

from pathlib import Path

from miaos.persona import (
    PersonalityGuard,
    create_persona_package,
    load_persona_package,
    validate_persona_package,
)


def _write_profile(path: Path) -> None:
    path.write_text(
        """
identity:
  role: Test cognitive executor
  default_locale: ru-RU
  biography_seed: Test seed
values:
  ranked:
    - honesty
    - curiosity
model_binding:
  provider: mock
  model_id: mock-test
  runtime_profile: macbook_air_m4_32gb
autonomy_contract:
  contract_id: test-contract
  path: autonomy/contract_ref.json
  autonomy_ceiling: L3
""".strip(),
        encoding="utf-8",
    )


def test_create_and_validate_minimal_persona_package(tmp_path: Path) -> None:
    """Creating a minimal package writes all mandatory MVP files."""
    profile = tmp_path / "persona.yaml"
    output = tmp_path / "mia-minimal"
    _write_profile(profile)

    package = create_persona_package(name="Mia", profile_path=profile, output_path=output)
    manifest = validate_persona_package(output)

    assert package.manifest.name == "Mia"
    assert manifest.persona_id == package.manifest.persona_id
    assert (output / "manifest.json").exists()
    assert (output / "personality" / "identity.json").exists()
    assert (output / "personality" / "values.json").exists()
    assert (output / "model_binding.json").exists()
    assert (output / "autonomy" / "contract_ref.json").exists()


def test_load_persona_package_preserves_profile_values(tmp_path: Path) -> None:
    """Loading a package reconstructs the persona card and binding."""
    profile = tmp_path / "persona.yaml"
    output = tmp_path / "mia-minimal"
    _write_profile(profile)
    create_persona_package(name="Mia", profile_path=profile, output_path=output)

    package = load_persona_package(output)

    assert package.card.identity.name == "Mia"
    assert package.card.identity.role == "Test cognitive executor"
    assert package.card.values == ["honesty", "curiosity"]
    assert package.model_binding.model_id == "mock-test"
    assert package.autonomy_contract_ref.autonomy_ceiling == "L3"


def test_personality_guard_builds_inference_context(tmp_path: Path) -> None:
    """PersonalityGuard includes identity, values, model, and contract anchors."""
    profile = tmp_path / "persona.yaml"
    output = tmp_path / "mia-minimal"
    _write_profile(profile)
    create_persona_package(name="Mia", profile_path=profile, output_path=output)
    package = load_persona_package(output)

    context = PersonalityGuard().build_inference_context(package)

    assert "Identity: Mia" in context
    assert "Values: honesty, curiosity" in context
    assert "Model id: mock-test" in context
    assert "Autonomy ceiling: L3" in context
