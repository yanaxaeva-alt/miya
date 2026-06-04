"""Smoke tests for the MiaOS command-line interface."""

from typer.testing import CliRunner

from miaos.cli import app


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
