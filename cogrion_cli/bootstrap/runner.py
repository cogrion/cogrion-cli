import json
import subprocess
import sys

from rich.console import Console

from .addons import (
    HelmAddon,
    KUBEBLOCKS_CRDS_URL,
    SNAPSHOT_CRD_URLS,
    helm_repos_for,
    make_external_dns,
    make_kubeblocks,
    make_traefik,
)
from .constants import (
    CPLANE_AGENT_CHART,
    COGRION_SYSTEM_NAMESPACE,
    ECR_PUBLIC_REGISTRY,
)
from .helm import ensure_helm_repos, helm_apply, is_externally_managed
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


def _ecr_login(region: str, dry_run: bool) -> None:
    console.print(f"\\[ecr] logging in to {ECR_PUBLIC_REGISTRY}")
    if dry_run:
        console.print("[yellow]\\[ecr] dry-run: skipping login[/yellow]")
        return
    token = subprocess.run(
        ["aws", "ecr-public", "get-login-password", "--region", "us-east-1"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    result = subprocess.run(
        ["helm", "registry", "login", ECR_PUBLIC_REGISTRY, "--username", "AWS", "--password-stdin"],
        input=token,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"[ecr] helm registry login failed:\n{result.stderr.strip()}")
    console.print("\\[ecr] login successful")


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
        ["aws", "s3api", "head-bucket", "--bucket", bucket], capture_output=True, text=True
    )
    if head.returncode == 0:
        console.print(f"\\[s3] bucket {bucket} already exists — skipping")
        return
    result = subprocess.run(
        [
            "aws",
            "s3api",
            "create-bucket",
            "--bucket",
            bucket,
            "--region",
            region,
            "--create-bucket-configuration",
            f"LocationConstraint={region}",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"[s3] failed to create bucket {bucket}:\n{result.stderr.strip()}")
    console.print(f"\\[s3] bucket {bucket} created")


def _install_addons(addons: list[HelmAddon], dry_run: bool) -> None:
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
        helm_apply(
            release=addon.release_name,
            namespace=addon.namespace,
            chart=addon.chart,
            version=addon.version,
            set_args=addon.set_args,
            values_yaml=addon.values_yaml,
            dry_run=dry_run,
        )


def run(
    token: str,
    cluster_name: str,
    region: str,
    control_plane_url: str,
    agent_version: str,
    traefik_subnets: str,
    dns_webhook_tag: str,
    kubeblocks_backup_bucket: str,
    kubeblocks_backup_region: str,
    tofu_backend_bucket: str,
    tofu_backend_region: str,
    dry_run: bool,
    auto_approve: bool,
    skip_tls_verify: bool,
) -> None:
    console.print()
    console.print("=" * 60)
    console.print("  Cogrion Cluster Bootstrap Plan")
    console.print("=" * 60)
    console.print(f"  Cluster              : {cluster_name}  ({region})")
    console.print(f"  Control plane        : {control_plane_url}")
    console.print(f"  Namespace (must exist): {COGRION_SYSTEM_NAMESPACE}")
    console.print("  Addons to install    : traefik, external-dns (+ dns-webhook), kubeblocks")
    console.print(
        f"  KubeBlocks backups   : s3://{kubeblocks_backup_bucket} ({kubeblocks_backup_region})"
    )
    console.print(f"  cplane-agent chart   : {agent_version}")
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
    )

    _copy_secret_to_namespace(
        secret_name="cluster-agent-credentials",
        src_namespace=COGRION_SYSTEM_NAMESPACE,
        dst_namespace="external-dns",
        dry_run=dry_run,
    )

    addons = [
        make_traefik(traefik_subnets),
        make_external_dns(control_plane_url, webhook_tag=dns_webhook_tag),
    ]
    _install_addons(addons, dry_run=dry_run)

    _ensure_s3_bucket(kubeblocks_backup_bucket, kubeblocks_backup_region, dry_run=dry_run)
    for url in SNAPSHOT_CRD_URLS:
        _apply_manifest_url(url, dry_run=dry_run)
    _apply_manifest_url(KUBEBLOCKS_CRDS_URL, dry_run=dry_run, server_side=True)
    _install_addons(
        [make_kubeblocks(kubeblocks_backup_bucket, kubeblocks_backup_region)], dry_run=dry_run
    )

    _ecr_login(region=region, dry_run=dry_run)

    helm_apply(
        release="cplane-agent",
        namespace=COGRION_SYSTEM_NAMESPACE,
        chart=CPLANE_AGENT_CHART,
        version=agent_version,
        set_args={
            "existingSecret": "cluster-agent-credentials",
            "serviceAccount.create": "false",
            "serviceAccount.name": "cplane-agent",
            "tofu.backendBucket": tofu_backend_bucket,
            "tofu.backendRegion": tofu_backend_region,
            "aws.region": region,
        },
        dry_run=dry_run,
    )

    console.print("[green]\\[bootstrap] complete[/green]")
