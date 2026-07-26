from typer.testing import CliRunner

from cogrion_cli.cli import app

runner = CliRunner(env={"COLUMNS": "200", "TERM": "dumb"})


def test_help_lists_subcommands():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "auth" in result.stdout
    assert "cluster" in result.stdout
    assert "deploy" in result.stdout


def test_cluster_bootstrap_requires_tofu_backend_bucket():
    result = runner.invoke(
        app,
        [
            "cluster",
            "bootstrap",
            "--token",
            "tok",
            "--cluster-name",
            "qd-platform-test",
            "--region",
            "ap-southeast-1",
            "--dry-run",
            "--auto-approve",
        ],
    )
    assert result.exit_code != 0
    assert "tofu-backend-bucket" in result.output.lower()


def test_cluster_bootstrap_help_lists_new_options():
    result = runner.invoke(app, ["cluster", "bootstrap", "--help"])
    assert result.exit_code == 0
    assert "--tofu-backend-bucket" in result.output
    assert "--kubeblocks-backup-bucket" in result.output


def test_cluster_upgrade_help_lists_new_options():
    result = runner.invoke(app, ["cluster", "upgrade", "--help"])
    assert result.exit_code == 0
    assert "--tofu-backend-bucket" in result.output
    assert "--kubeblocks-backup-bucket" in result.output
