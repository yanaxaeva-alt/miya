"""Smoke tests for the MiaOS command-line interface."""

from pathlib import Path

from typer.testing import CliRunner

from miaos.cli import app
from miaos.models import ModelManager, ModelRole

MODEL_SIZE_BYTES = 8_300_000_000
MODEL_CONTEXT_TOKENS = 32768


def test_help_displays_command_name() -> None:
    """The root command exposes a help screen."""
    runner = CliRunner()

    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "MiaOS Builder local runtime CLI" in result.output


def test_version_command_displays_package_version() -> None:
    """The version command prints the package version."""
    runner = CliRunner()

    result = runner.invoke(app, ["version"])

    assert result.exit_code == 0
    assert "miaos 0.1.0" in result.output


def test_version_option_displays_package_version() -> None:
    """The global version option prints the package version."""
    runner = CliRunner()

    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0
    assert "miaos 0.1.0" in result.output


def test_runtime_profiles_command_lists_bundled_profiles() -> None:
    """The runtime profiles command shows bundled hardware profiles."""
    runner = CliRunner()

    result = runner.invoke(app, ["runtime", "profiles"])

    assert result.exit_code == 0
    assert "macbook_air_m4_32gb" in result.output
    assert "macbook_pro_m4pro_48gb" in result.output


def test_runtime_inspect_command_prints_profile_json() -> None:
    """The runtime inspect command prints validated profile data."""
    runner = CliRunner()

    result = runner.invoke(app, ["runtime", "inspect", "--profile", "macbook_air_m4_32gb"])

    assert result.exit_code == 0
    assert '"name": "macbook_air_m4_32gb"' in result.output
    assert '"unified_memory_gb": 32' in result.output


def test_model_providers_command_lists_known_providers() -> None:
    """The model providers command shows mock and MLX providers."""
    runner = CliRunner()

    result = runner.invoke(app, ["model", "providers"])

    assert result.exit_code == 0
    assert "mock" in result.output
    assert "mlx" in result.output


def test_model_register_and_list_commands_use_sqlite_registry(tmp_path: Path) -> None:
    """The model register and list commands write to the configured SQLite DB."""
    runner = CliRunner()
    db_path = tmp_path / "models.sqlite3"

    register_result = runner.invoke(
        app,
        [
            "model",
            "register",
            "--repo",
            "local:test-model",
            "--family",
            "qwen",
            "--params-billion",
            "7",
            "--quant",
            "4bit",
            "--size-bytes",
            str(MODEL_SIZE_BYTES),
            "--context-len",
            str(MODEL_CONTEXT_TOKENS),
            "--path",
            "/models/test-model",
            "--pool-role",
            "worker",
            "--db",
            str(db_path),
        ],
    )
    list_result = runner.invoke(app, ["model", "list", "--db", str(db_path)])

    assert register_result.exit_code == 0
    assert list_result.exit_code == 0
    assert "local:test-model" in list_result.output
    assert "worker" in list_result.output


def test_model_inspect_command_prints_registered_record(tmp_path: Path) -> None:
    """The model inspect command prints one registered model as JSON."""
    runner = CliRunner()
    db_path = tmp_path / "models.sqlite3"
    manager = ModelManager.from_path(db_path)
    record = manager.register_model(
        repo="local:inspect-model",
        family="qwen",
        params_billion=7,
        quant="4bit",
        size_bytes=MODEL_SIZE_BYTES,
        context_len=MODEL_CONTEXT_TOKENS,
        path="/models/inspect-model",
        pool_role=ModelRole.WORKER,
    )

    result = runner.invoke(app, ["model", "inspect", record.id, "--db", str(db_path)])

    assert result.exit_code == 0
    assert '"repo":"local:inspect-model"' in result.output.replace(" ", "")


def test_persona_create_inspect_validate_commands(tmp_path: Path) -> None:
    """Persona CLI commands create and validate a minimal `.mia` directory."""
    runner = CliRunner()
    profile = tmp_path / "persona.yaml"
    output = tmp_path / "mia"
    profile.write_text(
        """
identity:
  role: CLI persona
values:
  ranked: [honesty, care]
model_binding:
  provider: mock
  model_id: mock-cli
autonomy_contract:
  contract_id: cli-contract
  autonomy_ceiling: L3
""".strip(),
        encoding="utf-8",
    )

    create_result = runner.invoke(
        app,
        [
            "persona",
            "create",
            "--name",
            "Mia",
            "--profile",
            str(profile),
            "--output",
            str(output),
        ],
    )
    inspect_result = runner.invoke(app, ["persona", "inspect", str(output)])
    validate_result = runner.invoke(app, ["persona", "validate", str(output)])

    assert create_result.exit_code == 0
    assert inspect_result.exit_code == 0
    assert validate_result.exit_code == 0
    assert '"name":"Mia"' in inspect_result.output.replace(" ", "")
    assert "Persona package is valid: Mia" in validate_result.output
