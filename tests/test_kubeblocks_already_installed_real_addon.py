import json
import subprocess

from cogrion_cli.bootstrap import helm
from cogrion_cli.bootstrap.addons import KUBEBLOCKS_VERSION, make_kubeblocks


def test_needs_upgrade_false_for_real_kubeblocks_addon_when_already_at_current_version(
    monkeypatch,
):
    """Reproduces the real bootstrap log: `helm get metadata kubeblocks`
    reports a chart version matching KUBEBLOCKS_VERSION exactly (including
    the "v" prefix, since that's the literal tag used both as the CRD
    download path and as the --version passed to `helm upgrade --install`)
    — needs_upgrade must say False so the CRD re-apply, helm upgrade, and
    rollout restart are all skipped."""

    def fake_run(cmd, **kwargs):
        if cmd[:3] == ["helm", "get", "metadata"]:
            payload = json.dumps({"chart": "kubeblocks", "version": KUBEBLOCKS_VERSION})
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout=payload, stderr="")
        raise AssertionError(f"unexpected subprocess call: {cmd}")

    monkeypatch.setattr(helm.subprocess, "run", fake_run)

    addon = make_kubeblocks(backup_bucket="w-prodsbx03-kb-backup", backup_region="ap-southeast-1")

    assert helm.needs_upgrade(addon) is False
