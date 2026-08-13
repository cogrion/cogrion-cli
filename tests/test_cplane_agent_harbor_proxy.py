from cogrion_cli.bootstrap import runner
from cogrion_cli.bootstrap.constants import CPLANE_AGENT_CHART
from cogrion_cli.bootstrap.register import RegistrationResult


def _run_kwargs(**overrides):
    kwargs = dict(
        provider="alicloud",
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
    monkeypatch.setattr(runner, "_check_namespace_exists", lambda *a, **k: None)
    monkeypatch.setattr(runner, "register_agent", lambda **k: RegistrationResult(skipped=True))
    monkeypatch.setattr(runner, "_copy_secret_to_namespace", lambda *a, **k: None)
    monkeypatch.setattr(runner, "_ensure_backup_bucket", lambda *a, **k: None)
    monkeypatch.setattr(runner, "_apply_manifest_url", lambda *a, **k: None)
    monkeypatch.setattr(runner, "needs_upgrade", lambda addon: False)
    monkeypatch.setattr(runner, "_rollout_restart", lambda *a, **k: None)


def test_no_ecr_login_symbol_left_in_runner():
    # The bootstrap chart moves through Harbor's public-ecr-proxy (an
    # anonymous-pull registry mirror), which needs no registry login at
    # all — direct public.ecr.aws access is being retired. Guards against
    # the old `aws ecr-public get-login-password` shell-out creeping back
    # in, which would break bootstrap on any non-AWS provider (no `aws`
    # CLI/credentials in the pod).
    assert not hasattr(runner, "_ecr_login")


def test_cplane_agent_chart_pulled_through_harbor_proxy(monkeypatch):
    assert "public.ecr.aws" not in CPLANE_AGENT_CHART
    assert CPLANE_AGENT_CHART.startswith(
        "oci://harbor.sgp.prod.cogrion.com/public-ecr-proxy/"
    )

    _patch_common(monkeypatch)
    installed = []
    monkeypatch.setattr(
        runner, "_install_addons", lambda addons, **k: installed.extend(addons)
    )

    runner.run(**_run_kwargs(provider="alicloud"))

    cplane_agent = next(a for a in installed if a.release_name == "cplane-agent")
    assert cplane_agent.chart == CPLANE_AGENT_CHART
