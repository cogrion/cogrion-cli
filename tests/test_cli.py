from typer.testing import CliRunner

from cogrion_cli.cli import app

runner = CliRunner()


def test_help_lists_subcommands():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "auth" in result.stdout
    assert "cluster" in result.stdout
    assert "deploy" in result.stdout
