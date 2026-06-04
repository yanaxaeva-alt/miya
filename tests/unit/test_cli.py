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
