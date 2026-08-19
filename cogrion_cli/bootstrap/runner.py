import json
import subprocess
import sys

from rich.console import Console

from .addons import (
    HelmAddon,
    KUBEBLOCKS_CRDS_URL,
    KUBEBLOCKS_NAMESPACE,
    SNAPSHOT_CRD_URLS,
    helm_repos_for,
    make_external_dns,
    make_kubeblocks,
)
from .constants import (
    CPLANE_AGENT_CHART,
    CPLANE_AGENT_DEFAULT_REPLICA_COUNT,
    CPLANE_AGENT_DEFAULT_SERVICE_ACCOUNT_NAME,
    CPLANE_AGENT_MIN_REPLICA_COUNT,
    COGRION_SYSTEM_NAMESPACE,
)
from .helm import ensure_helm_repos, helm_apply, is_externally_managed, needs_upgrade
from .register import register_agent

console = Console()


def _check_namespace_exists(namespace: str, dry_run: bool) -> None:
    """Read-only preflight — cogrion-cli no longer creates platform namespaces.

    They're provisioned by terraform-cogrion-aws-eks-managed-node-group
    alongside the IRSA roles/service-accounts this command relies on.
    """
    if dry_run:
        console.print(f"[yellow]\\[kubectl] dry-run: check namespace {namespace} exists[/yellow]")
        return
    result = subprocess.run(
        ["kubectl", "get", "namespace", namespace], capture_output=True, text=True
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"[kubectl] namespace '{namespace}' not found — run `tofu apply` in "
            "terraform-cogrion-aws-eks-managed-node-group first to provision the "
            "cluster's namespaces, IRSA roles, and service accounts."
        )
    console.print(f"\\[kubectl] namespace {namespace} found")


def _ensure_namespace(namespace: str, dry_run: bool) -> None:
    if dry_run:
        console.print(f"[yellow]\\[kubectl] dry-run: ensure namespace {namespace}[/yellow]")
        return
    result = subprocess.run(
        ["kubectl", "create", "namespace", namespace, "--dry-run=client", "-o", "yaml"],
        capture_output=True,
        check=True,
    )
    subprocess.run(["kubectl", "apply", "-f", "-"], input=result.stdout, check=True)
    console.print(f"\\[kubectl] namespace {namespace} ensured")


def _copy_secret_to_namespace(
    secret_name: str, src_namespace: str, dst_namespace: str, dry_run: bool
) -> None:
    if dry_run:
        console.print(
            f"[yellow]\\[kubectl] dry-run: copy secret {secret_name} "
            f"{src_namespace} -> {dst_namespace}[/yellow]"
        )
        return
    _ensure_namespace(dst_namespace, dry_run=False)
    get = subprocess.run(
        ["kubectl", "get", "secret", secret_name, "-n", src_namespace, "-o", "json"],
        capture_output=True,
        text=True,
        check=True,
    )
    secret = json.loads(get.stdout)
    secret["metadata"] = {"name": secret_name, "namespace": dst_namespace}
    apply = subprocess.run(
        ["kubectl", "apply", "-f", "-"], input=json.dumps(secret), text=True, capture_output=True
    )
    if apply.returncode != 0:
        raise RuntimeError(
            f"[kubectl] failed to copy secret {secret_name} to {dst_namespace}:\n"
            f"{apply.stderr.strip()}"
        )
    console.print(f"\\[kubectl] secret {secret_name} copied to namespace {dst_namespace}")


def _should_upgrade(addon: HelmAddon, dry_run: bool, force_upgrade: bool) -> bool:
    """Single, addon-agnostic decision point for whether to (re)install an
    addon — every caller that wants this gated (or bypassed) should go
    through here rather than re-deriving the condition inline. dry_run
    can't know the real cluster state, so it always says yes ("would
    upgrade"); force_upgrade is explicit operator intent to bypass the
    version check entirely (e.g. to force a reconcile/restart even though
    nothing changed); otherwise defer to needs_upgrade's real Helm-state
    comparison.

    Note this only compares chart identity/version, not `set_args`/
    `values_yaml` content — if an addon's values changed but its chart
    version didn't, re-running without --force-upgrade won't pick that up.
    That's the explicit trade-off: cheap, predictable no-op re-runs by
    default, with --force-upgrade as the escape hatch when values need to
    be reapplied despite an unchanged version."""
    return dry_run or force_upgrade or needs_upgrade(addon)


def _apply_manifest_url(url: str, dry_run: bool, server_side: bool = False) -> None:
    if dry_run:
        console.print(f"[yellow]\\[kubectl] dry-run: apply {url}[/yellow]")
        return
    cmd = ["kubectl", "apply"]
    if server_side:
        cmd += ["--server-side", "--force-conflicts"]
    cmd += ["-f", url]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"[kubectl] apply {url} failed:\n{result.stderr.strip()}")
    console.print(f"\\[kubectl] applied {url}")


def _ensure_s3_bucket(bucket: str, region: str, dry_run: bool) -> None:
    if dry_run:
        console.print(f"[yellow]\\[s3] dry-run: ensure bucket {bucket} ({region})[/yellow]")
        return
    head = subprocess.run(
        ["aws", "s3api", "head-bucket", "--bucket", bucket, "--region", region],
        capture_output=True,
        text=True,
    )
    if head.returncode == 0:
        console.print(f"\\[s3] bucket {bucket} already exists — adopting")
        return
    create_args = ["aws", "s3api", "create-bucket", "--bucket", bucket, "--region", region]
    if region != "us-east-1":
        create_args += ["--create-bucket-configuration", f"LocationConstraint={region}"]
    result = subprocess.run(create_args, capture_output=True, text=True)
    if result.returncode == 0:
        console.print(f"\\[s3] bucket {bucket} created")
        return
    if "BucketAlreadyExists" in result.stderr or "BucketAlreadyOwnedByYou" in result.stderr:
        console.print(f"\\[s3] bucket {bucket} already exists — adopting")
        return
    raise RuntimeError(f"[s3] failed to create bucket {bucket}:\n{result.stderr.strip()}")


def _ensure_oss_bucket(bucket: str, region: str, dry_run: bool) -> None:
    if dry_run:
        console.print(f"[yellow]\\[oss] dry-run: ensure bucket {bucket} ({region})[/yellow]")
        return
    stat = subprocess.run(
        ["aliyun", "oss", "stat", f"oss://{bucket}", "--region", region],
        capture_output=True,
        text=True,
    )
    if stat.returncode == 0:
        console.print(f"\\[oss] bucket {bucket} already exists — adopting")
        return
    result = subprocess.run(
        ["aliyun", "oss", "mb", f"oss://{bucket}", "--region", region],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        console.print(f"\\[oss] bucket {bucket} created")
        return
    if "BucketAlreadyExists" in result.stderr or "BucketAlreadyOwnedByYou" in result.stderr:
        console.print(f"\\[oss] bucket {bucket} already exists — adopting")
        return
    raise RuntimeError(f"[oss] failed to create bucket {bucket}:\n{result.stderr.strip()}")


def _ensure_backup_bucket(provider: str, bucket: str, region: str, dry_run: bool) -> None:
    if provider == "aws":
        _ensure_s3_bucket(bucket, region, dry_run=dry_run)
    elif provider == "alicloud":
        _ensure_oss_bucket(bucket, region, dry_run=dry_run)
    else:
        raise ValueError(f"_ensure_backup_bucket: unsupported provider {provider!r}")


def _rollout_restart(deployment: str, namespace: str, dry_run: bool) -> None:
    if dry_run:
        console.print(
            f"[yellow]\\[kubectl] dry-run: rollout restart deployment/{deployment} "
            f"-n {namespace}[/yellow]"
        )
        return
    restart = subprocess.run(
        ["kubectl", "rollout", "restart", f"deployment/{deployment}", "-n", namespace],
        capture_output=True,
        text=True,
    )
    if restart.returncode != 0:
        raise RuntimeError(
            f"[kubectl] rollout restart deployment/{deployment} -n {namespace} failed:\n"
            f"{restart.stderr.strip()}"
        )
    status = subprocess.run(
        [
            "kubectl",
            "rollout",
            "status",
            f"deployment/{deployment}",
            "-n",
            namespace,
            "--timeout=5m",
        ],
        capture_output=True,
        text=True,
    )
    if status.returncode != 0:
        raise RuntimeError(
            f"[kubectl] rollout status deployment/{deployment} -n {namespace} failed:\n"
            f"{status.stderr.strip()}"
        )
    console.print(f"\\[kubectl] deployment/{deployment} restarted and healthy")


def _install_addons(addons: list[HelmAddon], dry_run: bool, force_upgrade: bool = False) -> None:
    ensure_helm_repos(helm_repos_for(addons), dry_run=dry_run)
    for addon in addons:
        if addon.detect and not dry_run:
            kind, name = addon.detect
            if is_externally_managed(kind, name, addon.namespace):
                console.print(
                    f"[yellow]\\[bootstrap] {addon.release_name} already installed "
                    "outside Helm — skipping[/yellow]"
                )
                continue
        if not _should_upgrade(addon, dry_run=dry_run, force_upgrade=force_upgrade):
            console.print(
                f"\\[helm] {addon.release_name} already at version {addon.version} — skipping"
            )
            continue
        helm_apply(
            release=addon.release_name,
            namespace=addon.namespace,
            chart=addon.chart,
            version=addon.version,
            set_args=addon.set_args,
            values_yaml=addon.values_yaml,
            dry_run=dry_run,
        )


_BACKUP_BUCKET_SCHEME = {
    "aws": "s3",
    "alicloud": "oss",
}


def run(
    token: str,
    cluster_name: str,
    region: str,
    control_plane_url: str,
    agent_version: str,
    dns_webhook_tag: str,
    kubeblocks_backup_bucket: str,
    kubeblocks_backup_region: str,
    tofu_backend_bucket: str,
    tofu_backend_region: str,
    dry_run: bool,
    auto_approve: bool,
    skip_tls_verify: bool,
    provider: str,
    agent_service_account_name: str = CPLANE_AGENT_DEFAULT_SERVICE_ACCOUNT_NAME,
    agent_replica_count: int = CPLANE_AGENT_DEFAULT_REPLICA_COUNT,
    force_register: bool = False,
    force_upgrade: bool = False,
) -> None:
    if provider not in _BACKUP_BUCKET_SCHEME:
        raise ValueError(f"run: unsupported provider {provider!r}")
    if agent_replica_count < CPLANE_AGENT_MIN_REPLICA_COUNT:
        raise ValueError(
            f"run: --agent-replica-count must be >= {CPLANE_AGENT_MIN_REPLICA_COUNT} "
            f"(got {agent_replica_count})"
        )

    console.print()
    console.print("=" * 60)
    console.print("  Cogrion Cluster Bootstrap Plan")
    console.print("=" * 60)
    console.print(f"  Cluster              : {cluster_name}  ({region})")
    console.print(f"  Control plane        : {control_plane_url}")
    console.print(f"  Namespace (must exist): {COGRION_SYSTEM_NAMESPACE}")
    console.print("  Addons to install    : external-dns (+ dns-webhook), kubeblocks")
    console.print(
        f"  KubeBlocks backups   : {_BACKUP_BUCKET_SCHEME[provider]}://{kubeblocks_backup_bucket} "
        f"({kubeblocks_backup_region})"
    )
    console.print(f"  cplane-agent chart   : {agent_version}")
    console.print(f"  cplane-agent replicas: {agent_replica_count}")
    console.print("=" * 60)
    console.print()

    if auto_approve:
        console.print("  --auto-approve set — skipping confirmation.")
    else:
        console.print("  Only 'yes' will be accepted to approve.")
        answer = input("  Enter a value: ").strip()
        if answer != "yes":
            console.print("\n[red]Error: Bootstrap cancelled.[/red]")
            sys.exit(1)

    _check_namespace_exists(COGRION_SYSTEM_NAMESPACE, dry_run=dry_run)

    register_agent(
        control_plane_url=control_plane_url,
        token=token,
        namespace=COGRION_SYSTEM_NAMESPACE,
        dry_run=dry_run,
        skip_tls_verify=skip_tls_verify,
        cluster_name=cluster_name,
        region=region,
        provider=provider,
        force_register=force_register,
    )

    _copy_secret_to_namespace(
        secret_name="cluster-agent-credentials",
        src_namespace=COGRION_SYSTEM_NAMESPACE,
        dst_namespace="external-dns",
        dry_run=dry_run,
    )

    addons = [make_external_dns(control_plane_url, webhook_tag=dns_webhook_tag)]
    _install_addons(addons, dry_run=dry_run, force_upgrade=force_upgrade)

    _ensure_backup_bucket(
        provider, kubeblocks_backup_bucket, kubeblocks_backup_region, dry_run=dry_run
    )
    kubeblocks_addon = make_kubeblocks(
        kubeblocks_backup_bucket, kubeblocks_backup_region, provider=provider
    )
    if _should_upgrade(kubeblocks_addon, dry_run=dry_run, force_upgrade=force_upgrade):
        for url in SNAPSHOT_CRD_URLS:
            _apply_manifest_url(url, dry_run=dry_run)
        _apply_manifest_url(KUBEBLOCKS_CRDS_URL, dry_run=dry_run, server_side=True)
        _install_addons([kubeblocks_addon], dry_run=dry_run, force_upgrade=force_upgrade)
        for deployment in ("kubeblocks", "kubeblocks-dataprotection"):
            _rollout_restart(deployment, namespace=KUBEBLOCKS_NAMESPACE, dry_run=dry_run)
    else:
        console.print(
            f"\\[kubeblocks] already at version {kubeblocks_addon.version} — "
            "skipping CRD re-apply, helm upgrade, and rollout restart"
        )

    # agent.provider lets tofu-run.ts know, once per deployment (not per
    # resource), whether it needs to exchange RRSA for STS credentials
    # before `tofu init` — Alicloud's oss backend has no OIDC support,
    # unlike AWS's s3 backend. Mirrors KCL's t.CloudProviderEnum values.
    cloud_set_args = {}
    if provider == "aws":
        cloud_set_args["aws.region"] = region
        cloud_set_args["agent.provider"] = "AWS_EKS"
    elif provider == "alicloud":
        cloud_set_args["alicloud.regionId"] = region
        cloud_set_args["agent.provider"] = "ALICLOUD_ACK"
    else:
        raise ValueError(f"run: unsupported provider {provider!r}")

    cplane_agent_addon = HelmAddon(
        release_name="cplane-agent",
        namespace=COGRION_SYSTEM_NAMESPACE,
        chart=CPLANE_AGENT_CHART,
        version=agent_version,
        set_args={
            "existingSecret": "cluster-agent-credentials",
            "serviceAccount.create": "false",
            "serviceAccount.name": agent_service_account_name,
            "replicaCount": str(agent_replica_count),
            "tofu.backendBucket": tofu_backend_bucket,
            "tofu.backendRegion": tofu_backend_region,
            **cloud_set_args,
        },
    )
    _install_addons([cplane_agent_addon], dry_run=dry_run, force_upgrade=force_upgrade)

    console.print("[green]\\[bootstrap] complete[/green]")
