import subprocess

import pytest
import typer

from cogrion_cli.bootstrap import register, runner
from cogrion_cli.bootstrap.addons import make_kubeblocks
from cogrion_cli.commands.cluster import _validate_provider


def test_validate_provider_accepts_alicloud():
    _validate_provider("alicloud")  # must not raise


def test_validate_provider_rejects_gcp():
    with pytest.raises(typer.Exit):
        _validate_provider("gcp")


def test_make_kubeblocks_uses_oss_storage_provider_and_endpoint_for_alicloud():
    addon = make_kubeblocks(
        backup_bucket="w-prodsbx03-kb-backup", backup_region="ap-southeast-7", provider="alicloud"
    )

    assert 'storageProvider: "oss"' in addon.values_yaml
    assert 'endpoint: "oss-ap-southeast-7.aliyuncs.com"' in addon.values_yaml
    assert "bucket: w-prodsbx03-kb-backup" in addon.values_yaml


def test_make_kubeblocks_uses_s3_storage_provider_and_empty_endpoint_for_aws():
    addon = make_kubeblocks(
        backup_bucket="w-prodsbx03-kb-backup", backup_region="ap-southeast-1", provider="aws"
    )

    assert 'storageProvider: "s3"' in addon.values_yaml
    assert 'endpoint: ""' in addon.values_yaml


def test_make_kubeblocks_rejects_unsupported_provider():
    with pytest.raises(ValueError):
        make_kubeblocks(backup_bucket="b", backup_region="r", provider="gcp")


def test_ensure_backup_bucket_uses_aliyun_oss_for_alicloud(monkeypatch):
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        if cmd[:3] == ["aliyun", "oss", "stat"]:
            return subprocess.CompletedProcess(args=cmd, returncode=1, stdout="", stderr="")
        if cmd[:3] == ["aliyun", "oss", "mb"]:
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")
        raise AssertionError(f"unexpected subprocess call: {cmd}")

    monkeypatch.setattr(runner.subprocess, "run", fake_run)

    runner._ensure_backup_bucket("alicloud", "my-bucket", "ap-southeast-7", dry_run=False)

    assert ["aliyun", "oss", "stat", "oss://my-bucket", "--region", "ap-southeast-7"] in calls
    assert ["aliyun", "oss", "mb", "oss://my-bucket", "--region", "ap-southeast-7"] in calls


def test_ensure_backup_bucket_adopts_existing_oss_bucket(monkeypatch, capsys):
    def fake_run(cmd, **kwargs):
        if cmd[:3] == ["aliyun", "oss", "stat"]:
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")
        raise AssertionError(f"unexpected subprocess call (should not create): {cmd}")

    monkeypatch.setattr(runner.subprocess, "run", fake_run)

    runner._ensure_backup_bucket("alicloud", "my-bucket", "ap-southeast-7", dry_run=False)

    assert "already exists" in capsys.readouterr().out.lower()


def test_ensure_backup_bucket_rejects_unsupported_provider():
    with pytest.raises(ValueError):
        runner._ensure_backup_bucket("gcp", "bucket", "region", dry_run=True)


def test_run_uses_alicloud_regionid_set_arg_for_cplane_agent(capsys):
    runner.run(
        provider="alicloud",
        token="tok",
        cluster_name="c50f7af290a5a458698e0c3c9934de15d",
        region="ap-southeast-7",
        control_plane_url="https://cplane.example.com",
        agent_version="0.1.0",
        dns_webhook_tag="0.1.0",
        dry_run=True,
        auto_approve=True,
        skip_tls_verify=False,
        kubeblocks_backup_bucket="w-test-kb-backup",
        kubeblocks_backup_region="ap-southeast-7",
        tofu_backend_bucket="w-test-tfstate",
        tofu_backend_region="ap-southeast-7",
    )
    out = capsys.readouterr().out.lower()
    assert "alicloud.regionid=ap-southeast-7" in out
    assert "agent.provider=alicloud_ack" in out
    assert "aws.region" not in out
    assert "oss://w-test-kb-backup" in out


def test_run_defaults_cplane_agent_to_two_replicas(capsys):
    runner.run(
        provider="alicloud",
        token="tok",
        cluster_name="c50f7af290a5a458698e0c3c9934de15d",
        region="ap-southeast-7",
        control_plane_url="https://cplane.example.com",
        agent_version="0.1.0",
        dns_webhook_tag="0.1.0",
        dry_run=True,
        auto_approve=True,
        skip_tls_verify=False,
        kubeblocks_backup_bucket="w-test-kb-backup",
        kubeblocks_backup_region="ap-southeast-7",
        tofu_backend_bucket="w-test-tfstate",
        tofu_backend_region="ap-southeast-7",
    )
    out = capsys.readouterr().out.lower()
    assert "replicacount=2" in out
    assert "autoscaling.minreplicas=2" in out


def test_run_passes_agent_replica_count_to_cplane_agent_set_args(capsys):
    runner.run(
        provider="alicloud",
        token="tok",
        cluster_name="c50f7af290a5a458698e0c3c9934de15d",
        region="ap-southeast-7",
        control_plane_url="https://cplane.example.com",
        agent_version="0.1.0",
        dns_webhook_tag="0.1.0",
        dry_run=True,
        auto_approve=True,
        skip_tls_verify=False,
        kubeblocks_backup_bucket="w-test-kb-backup",
        kubeblocks_backup_region="ap-southeast-7",
        tofu_backend_bucket="w-test-tfstate",
        tofu_backend_region="ap-southeast-7",
        agent_replica_count=3,
    )
    out = capsys.readouterr().out.lower()
    assert "replicacount=3" in out


def test_run_rejects_replica_count_below_minimum():
    with pytest.raises(ValueError):
        runner.run(
            provider="alicloud",
            token="tok",
            cluster_name="c",
            region="ap-southeast-7",
            control_plane_url="https://cplane.example.com",
            agent_version="0.1.0",
            dns_webhook_tag="0.1.0",
            dry_run=True,
            auto_approve=True,
            skip_tls_verify=False,
            kubeblocks_backup_bucket="b",
            kubeblocks_backup_region="ap-southeast-7",
            tofu_backend_bucket="b",
            tofu_backend_region="ap-southeast-7",
            agent_replica_count=0,
        )


def test_run_rejects_unsupported_provider():
    with pytest.raises(ValueError):
        runner.run(
            provider="gcp",
            token="tok",
            cluster_name="c",
            region="r",
            control_plane_url="https://cplane.example.com",
            agent_version="0.1.0",
            dns_webhook_tag="0.1.0",
            dry_run=True,
            auto_approve=True,
            skip_tls_verify=False,
            kubeblocks_backup_bucket="b",
            kubeblocks_backup_region="r",
            tofu_backend_bucket="b",
            tofu_backend_region="r",
        )


def test_discover_oidc_issuer_alicloud_uses_first_issuer_from_rrsa_config(monkeypatch, tmp_path):
    # No SA token on disk in the test environment, so this exercises the
    # local-dev fallback path — same as the AWS eks describe-cluster case.
    monkeypatch.setattr(register, "SA_TOKEN_PATH", str(tmp_path / "does-not-exist"))

    detail_json = (
        '{"rrsa_config": {"issuer": '
        '"https://oidc-ack-ap-southeast-7.oss-ap-southeast-7.aliyuncs.com/CLUSTERID,'
        'https://kubernetes.default.svc"}}'
    )

    def fake_run(cmd, **kwargs):
        assert cmd == ["aliyun", "cs", "DescribeClusterDetail", "--ClusterId", "CLUSTERID"]
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout=detail_json, stderr="")

    monkeypatch.setattr(register.subprocess, "run", fake_run)

    issuer = register._discover_oidc_issuer(
        provider="alicloud", cluster_name="CLUSTERID", region="ap-southeast-7"
    )

    assert issuer == "https://oidc-ack-ap-southeast-7.oss-ap-southeast-7.aliyuncs.com/CLUSTERID"


def test_discover_oidc_issuer_rejects_unsupported_provider(monkeypatch, tmp_path):
    monkeypatch.setattr(register, "SA_TOKEN_PATH", str(tmp_path / "does-not-exist"))

    with pytest.raises(ValueError):
        register._discover_oidc_issuer(provider="gcp", cluster_name="c", region="r")
