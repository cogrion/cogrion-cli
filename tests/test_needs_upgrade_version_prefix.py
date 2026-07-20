import json
import subprocess

from cogrion_cli.bootstrap import helm
from cogrion_cli.bootstrap.addons import KUBEBLOCKS_VERSION, make_kubeblocks


def test_needs_upgrade_false_when_installed_version_differs_only_by_v_prefix(monkeypatch):
    """KUBEBLOCKS_VERSION ("v1.0.2") is a GitHub release tag reused as the
    Helm --version flag — but Helm's internal semver handling normalizes
    away a leading "v" when it resolves the chart, so the version Helm
    actually records in `helm status`'s chart.metadata.version can come back
    as "1.0.2" (no "v") even though the install used "v1.0.2". A naive exact
    string comparison sees that as a permanent mismatch and treats an
    already-current release as always needing (re)installation forever —
    which is the actual behavior observed on w-prodsbx03: CRD re-apply,
    helm upgrade, and rollout restart all ran even though kubeblocks was
    already deployed at the target version."""
    installed_version_without_v_prefix = KUBEBLOCKS_VERSION.lstrip("v")
    assert (
        installed_version_without_v_prefix != KUBEBLOCKS_VERSION
    )  # sanity: prefix actually differs

    def fake_run(cmd, **kwargs):
        if cmd[:3] == ["helm", "get", "metadata"]:
            payload = json.dumps(
                {"chart": "kubeblocks", "version": installed_version_without_v_prefix}
            )
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout=payload, stderr="")
        raise AssertionError(f"unexpected subprocess call: {cmd}")

    monkeypatch.setattr(helm.subprocess, "run", fake_run)

    addon = make_kubeblocks(backup_bucket="w-prodsbx03-kb-backup", backup_region="ap-southeast-1")

    assert helm.needs_upgrade(addon) is False
