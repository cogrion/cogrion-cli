from cogrion_cli.bootstrap import runner


def _run_kwargs(**overrides):
    kwargs = dict(
        provider="aws",
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


def test_force_upgrade_bypasses_needs_upgrade_gate_even_when_up_to_date(monkeypatch):
    restart_calls = _patch_common(monkeypatch)
    # needs_upgrade says "nothing to do" — force_upgrade must override that.
    monkeypatch.setattr(runner, "needs_upgrade", lambda addon: False)

    runner.run(**_run_kwargs(force_upgrade=True))

    assert restart_calls == ["kubeblocks", "kubeblocks-dataprotection"]


def test_without_force_upgrade_still_skips_when_up_to_date(monkeypatch, capsys):
    restart_calls = _patch_common(monkeypatch)
    monkeypatch.setattr(runner, "needs_upgrade", lambda addon: False)

    runner.run(**_run_kwargs(force_upgrade=False))

    assert restart_calls == []
    assert "skipping CRD re-apply" in capsys.readouterr().out
