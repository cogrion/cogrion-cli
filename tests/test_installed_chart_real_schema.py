import json
import subprocess

from cogrion_cli.bootstrap import helm
from cogrion_cli.bootstrap.addons import make_kubeblocks

# Captured live from `helm get metadata kubeblocks -n kb-system -o json`
# against w-prodsbx03 (Helm v3.18.6). `helm status -o json` on this same
# Helm version has NO "chart" key at all, which is what installed_chart()
# was wrongly assuming — this is the real, correct shape.
REAL_HELM_GET_METADATA_OUTPUT = json.dumps(
    {
        "name": "kubeblocks",
        "chart": "kubeblocks",
        "version": "1.0.2",
        "appVersion": "1.0.2",
        "annotations": {
            "artifacthub.io/changes": "",
            "artifacthub.io/links": "",
            "artifacthub.io/operator": "true",
            "artifacthub.io/prerelease": "true",
        },
        "namespace": "kb-system",
        "revision": 5,
        "status": "deployed",
        "deployedAt": "2026-07-20T07:50:55+07:00",
    }
)


def _fake_run_real_metadata(cmd, **kwargs):
    if cmd[:3] == ["helm", "get", "metadata"]:
        return subprocess.CompletedProcess(
            args=cmd, returncode=0, stdout=REAL_HELM_GET_METADATA_OUTPUT, stderr=""
        )
    raise AssertionError(f"unexpected subprocess call: {cmd}")


def test_installed_chart_parses_real_helm_get_metadata_output(monkeypatch):
    monkeypatch.setattr(helm.subprocess, "run", _fake_run_real_metadata)

    name, version = helm.installed_chart("kubeblocks", "kb-system")

    assert name == "kubeblocks"
    assert version == "1.0.2"


def test_needs_upgrade_false_for_real_kubeblocks_addon_against_real_schema(monkeypatch):
    monkeypatch.setattr(helm.subprocess, "run", _fake_run_real_metadata)

    addon = make_kubeblocks(backup_bucket="w-prodsbx03-kb-backup", backup_region="ap-southeast-1")

    assert helm.needs_upgrade(addon) is False
