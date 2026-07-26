import json
import subprocess

from cogrion_cli.bootstrap import helm, runner
from cogrion_cli.bootstrap.addons import HelmAddon


def _fake_helm_status(name: str | None, version: str | None = None):
    # Mocks `helm get metadata`, not `helm status` — helm status -o json has
    # no "chart" key on Helm v3.18.6 (verified against a live cluster).
    def fake_run(cmd, **kwargs):
        if cmd[:3] == ["helm", "get", "metadata"]:
            if name is None:
                return subprocess.CompletedProcess(
                    args=cmd, returncode=1, stdout="", stderr="not found"
                )
            payload = json.dumps({"chart": name, "version": version})
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout=payload, stderr="")
        raise AssertionError(f"unexpected subprocess call: {cmd}")

    return fake_run


def test_needs_upgrade_false_when_name_and_version_match(monkeypatch):
    monkeypatch.setattr(helm.subprocess, "run", _fake_helm_status("kubeblocks", "1.0.2"))
    addon = HelmAddon(
        release_name="kubeblocks",
        namespace="kb-system",
        chart="kubeblocks/kubeblocks",
        version="1.0.2",
    )

    assert helm.needs_upgrade(addon) is False


def test_needs_upgrade_true_when_installed_version_differs(monkeypatch):
    monkeypatch.setattr(helm.subprocess, "run", _fake_helm_status("kubeblocks", "1.0.1"))
    addon = HelmAddon(
        release_name="kubeblocks",
        namespace="kb-system",
        chart="kubeblocks/kubeblocks",
        version="1.0.2",
    )

    assert helm.needs_upgrade(addon) is True


def test_needs_upgrade_true_when_installed_chart_name_differs(monkeypatch):
    # Same release name, same version string, but a different chart entirely —
    # e.g. this release name got repointed at another chart. A version-only
    # check would wrongly call this "up to date"; comparing chart identity
    # (name) too catches it.
    monkeypatch.setattr(helm.subprocess, "run", _fake_helm_status("some-other-chart", "1.0.2"))
    addon = HelmAddon(
        release_name="kubeblocks",
        namespace="kb-system",
        chart="kubeblocks/kubeblocks",
        version="1.0.2",
    )

    assert helm.needs_upgrade(addon) is True


def test_needs_upgrade_true_when_not_installed(monkeypatch):
    monkeypatch.setattr(helm.subprocess, "run", _fake_helm_status(None))
    addon = HelmAddon(
        release_name="kubeblocks",
        namespace="kb-system",
        chart="kubeblocks/kubeblocks",
        version="1.0.2",
    )

    assert helm.needs_upgrade(addon) is True


def _run_kwargs(**overrides):
    kwargs = dict(
        token="tok",
        cluster_name="qd-platform-test",
        region="ap-southeast-1",
        control_plane_url="https://cplane.example.com",
        agent_version="0.1.0",
        dns_webhook_tag="0.1.0",
        dry_run=False,
        auto_approve=True,
        skip_tls_verify=False,
        kubeblocks_backup_bucket="qd-platform-test-kb-backup",
        kubeblocks_backup_region="ap-southeast-1",
        tofu_backend_bucket="qd-platform-test-tfstate",
        tofu_backend_region="ap-southeast-1",
    )
    kwargs.update(overrides)
    return kwargs


def _patch_common(monkeypatch):
    from cogrion_cli.bootstrap.register import RegistrationResult

    monkeypatch.setattr(runner, "_check_namespace_exists", lambda *a, **k: None)
    monkeypatch.setattr(runner, "register_agent", lambda **k: RegistrationResult(skipped=True))
    monkeypatch.setattr(runner, "_copy_secret_to_namespace", lambda *a, **k: None)
    monkeypatch.setattr(runner, "_install_addons", lambda *a, **k: None)
    monkeypatch.setattr(runner, "_ensure_s3_bucket", lambda *a, **k: None)
    monkeypatch.setattr(runner, "_apply_manifest_url", lambda *a, **k: None)
    monkeypatch.setattr(runner, "_ecr_login", lambda *a, **k: None)
    monkeypatch.setattr(runner, "helm_apply", lambda *a, **k: None)

    restart_calls = []
    monkeypatch.setattr(
        runner,
        "_rollout_restart",
        lambda deployment, namespace, dry_run: restart_calls.append(deployment),
    )
    return restart_calls


def test_run_skips_kubeblocks_work_when_already_at_desired_version(monkeypatch, capsys):
    restart_calls = _patch_common(monkeypatch)
    monkeypatch.setattr(runner, "needs_upgrade", lambda addon: False)

    runner.run(**_run_kwargs())

    assert restart_calls == []
    assert "skipping CRD re-apply" in capsys.readouterr().out


def test_run_does_kubeblocks_work_when_version_differs(monkeypatch):
    restart_calls = _patch_common(monkeypatch)
    monkeypatch.setattr(runner, "needs_upgrade", lambda addon: True)

    runner.run(**_run_kwargs())

    assert restart_calls == ["kubeblocks", "kubeblocks-dataprotection"]


def test_run_dry_run_always_does_kubeblocks_work_even_if_needs_upgrade_would_say_no(monkeypatch):
    restart_calls = _patch_common(monkeypatch)
    # Simulates dry_run's real behavior: needs_upgrade is never even consulted
    # for the branch decision, since dry_run short-circuits to "would upgrade".
    monkeypatch.setattr(runner, "needs_upgrade", lambda addon: False)

    runner.run(**_run_kwargs(dry_run=True))

    assert restart_calls == ["kubeblocks", "kubeblocks-dataprotection"]
