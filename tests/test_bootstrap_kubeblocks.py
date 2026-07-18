from cogrion_cli.bootstrap import runner


def test_run_dry_run_installs_kubeblocks(capsys):
    runner.run(
        token="tok",
        cluster_name="qd-platform-test",
        region="ap-southeast-1",
        control_plane_url="https://cplane.example.com",
        agent_version="0.1.0",
        traefik_subnets="subnet-a,subnet-b",
        dns_webhook_tag="0.1.0",
        dry_run=True,
        auto_approve=True,
        skip_tls_verify=False,
        kubeblocks_backup_bucket="qd-platform-test-kb-backup",
        kubeblocks_backup_region="ap-southeast-1",
        tofu_backend_bucket="qd-platform-test-tfstate",
        tofu_backend_region="ap-southeast-1",
    )
    out = capsys.readouterr().out.lower()
    assert "kubeblocks" in out
    assert "snapshot" in out
    assert "qd-platform-test-kb-backup" in out


def test_run_dry_run_sets_cplane_agent_tofu_backend(capsys):
    runner.run(
        token="tok",
        cluster_name="qd-platform-test",
        region="ap-southeast-1",
        control_plane_url="https://cplane.example.com",
        agent_version="0.1.0",
        traefik_subnets="subnet-a,subnet-b",
        dns_webhook_tag="0.1.0",
        dry_run=True,
        auto_approve=True,
        skip_tls_verify=False,
        kubeblocks_backup_bucket="qd-platform-test-kb-backup",
        kubeblocks_backup_region="ap-southeast-1",
        tofu_backend_bucket="qd-platform-test-tfstate",
        tofu_backend_region="ap-southeast-1",
    )
    out = capsys.readouterr().out.lower()
    assert "tofu.backendbucket=qd-platform-test-tfstate" in out
