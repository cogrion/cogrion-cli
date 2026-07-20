from cogrion_cli.bootstrap import runner
from cogrion_cli.bootstrap.addons import HelmAddon


def _addon(**overrides):
    kwargs = dict(
        release_name="traefik",
        namespace="traefik",
        chart="traefik/traefik",
        version="41.0.2",
    )
    kwargs.update(overrides)
    return HelmAddon(**kwargs)


def test_install_addons_skips_helm_apply_when_up_to_date(monkeypatch, capsys):
    monkeypatch.setattr(runner, "ensure_helm_repos", lambda *a, **k: None)
    monkeypatch.setattr(runner, "needs_upgrade", lambda addon: False)
    calls = []
    monkeypatch.setattr(runner, "helm_apply", lambda **k: calls.append(k))

    runner._install_addons([_addon()], dry_run=False, force_upgrade=False)

    assert calls == []
    assert "skipping" in capsys.readouterr().out.lower()


def test_install_addons_calls_helm_apply_when_needs_upgrade(monkeypatch):
    monkeypatch.setattr(runner, "ensure_helm_repos", lambda *a, **k: None)
    monkeypatch.setattr(runner, "needs_upgrade", lambda addon: True)
    calls = []
    monkeypatch.setattr(runner, "helm_apply", lambda **k: calls.append(k))

    runner._install_addons([_addon()], dry_run=False, force_upgrade=False)

    assert len(calls) == 1
    assert calls[0]["release"] == "traefik"


def test_install_addons_force_upgrade_bypasses_up_to_date_skip(monkeypatch):
    monkeypatch.setattr(runner, "ensure_helm_repos", lambda *a, **k: None)
    monkeypatch.setattr(runner, "needs_upgrade", lambda addon: False)
    calls = []
    monkeypatch.setattr(runner, "helm_apply", lambda **k: calls.append(k))

    runner._install_addons([_addon()], dry_run=False, force_upgrade=True)

    assert len(calls) == 1


def test_install_addons_dry_run_always_calls_helm_apply(monkeypatch):
    monkeypatch.setattr(runner, "ensure_helm_repos", lambda *a, **k: None)
    monkeypatch.setattr(runner, "needs_upgrade", lambda addon: False)
    calls = []
    monkeypatch.setattr(runner, "helm_apply", lambda **k: calls.append(k))

    runner._install_addons([_addon()], dry_run=True, force_upgrade=False)

    assert len(calls) == 1


def test_install_addons_externally_managed_skip_takes_priority_over_gating(monkeypatch, capsys):
    # An externally-managed resource must never be touched, force_upgrade or not.
    monkeypatch.setattr(runner, "ensure_helm_repos", lambda *a, **k: None)
    monkeypatch.setattr(runner, "is_externally_managed", lambda *a, **k: True)
    monkeypatch.setattr(runner, "needs_upgrade", lambda addon: True)
    calls = []
    monkeypatch.setattr(runner, "helm_apply", lambda **k: calls.append(k))

    addon = _addon(detect=("deployment", "traefik"))
    runner._install_addons([addon], dry_run=False, force_upgrade=True)

    assert calls == []
    assert "outside helm" in capsys.readouterr().out.lower()


def test_run_gates_cplane_agent_through_install_addons_style_check(monkeypatch):
    """cplane-agent's helm_apply used to run unconditionally at the end of
    run() — it must now go through the same needs_upgrade/force_upgrade
    gate as every other addon, not be a special case."""
    from cogrion_cli.bootstrap.register import RegistrationResult

    monkeypatch.setattr(runner, "_check_namespace_exists", lambda *a, **k: None)
    monkeypatch.setattr(runner, "register_agent", lambda **k: RegistrationResult(skipped=True))
    monkeypatch.setattr(runner, "_copy_secret_to_namespace", lambda *a, **k: None)
    monkeypatch.setattr(runner, "_ensure_s3_bucket", lambda *a, **k: None)
    monkeypatch.setattr(runner, "_apply_manifest_url", lambda *a, **k: None)
    monkeypatch.setattr(runner, "_rollout_restart", lambda *a, **k: None)
    monkeypatch.setattr(runner, "_ecr_login", lambda *a, **k: None)
    monkeypatch.setattr(runner, "ensure_helm_repos", lambda *a, **k: None)
    monkeypatch.setattr(runner, "is_externally_managed", lambda *a, **k: False)
    # Everything, including cplane-agent, reports already up to date.
    monkeypatch.setattr(runner, "needs_upgrade", lambda addon: False)

    calls = []
    monkeypatch.setattr(runner, "helm_apply", lambda **k: calls.append(k))

    runner.run(
        token="tok",
        cluster_name="qd-platform-test",
        region="ap-southeast-1",
        control_plane_url="https://cplane.example.com",
        agent_version="0.1.0",
        traefik_subnets="subnet-a,subnet-b",
        dns_webhook_tag="0.1.0",
        dry_run=False,
        auto_approve=True,
        skip_tls_verify=False,
        kubeblocks_backup_bucket="qd-platform-test-kb-backup",
        kubeblocks_backup_region="ap-southeast-1",
        tofu_backend_bucket="qd-platform-test-tfstate",
        tofu_backend_region="ap-southeast-1",
        force_upgrade=False,
    )

    # traefik, external-dns, kubeblocks, and cplane-agent are all "up to
    # date" per the mocked needs_upgrade — none of them should have called
    # helm_apply.
    assert calls == []
