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
        dry_run=True,
        auto_approve=True,
        skip_tls_verify=False,
        kubeblocks_backup_bucket="qd-platform-test-kb-backup",
        kubeblocks_backup_region="ap-southeast-1",
        tofu_backend_bucket="qd-platform-test-tfstate",
        tofu_backend_region="ap-southeast-1",
    )
    kwargs.update(overrides)
    return kwargs


def test_run_defaults_agent_service_account_name_to_cplane_agent(capsys):
    runner.run(**_run_kwargs())

    out = capsys.readouterr().out.lower()
    assert "serviceaccount.name=cplane-agent" in out


def test_run_honors_custom_agent_service_account_name(capsys):
    runner.run(**_run_kwargs(agent_service_account_name="my-custom-sa"))

    out = capsys.readouterr().out.lower()
    assert "serviceaccount.name=my-custom-sa" in out
    assert "serviceaccount.name=cplane-agent" not in out
