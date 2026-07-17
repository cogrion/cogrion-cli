import typer
from rich.console import Console

from cogrion_cli.bootstrap import runner
from cogrion_cli.bootstrap.addons import DNS_WEBHOOK_VERSION
from cogrion_cli.bootstrap.constants import CPLANE_AGENT_DEFAULT_VERSION, CPLANE_API_URL

app = typer.Typer(help="Manage your self-hosted cloud clusters")
console = Console()

_SUPPORTED_PROVIDERS = {"aws"}


def _validate_provider(provider: str) -> None:
    if provider not in _SUPPORTED_PROVIDERS:
        console.print(f"[red]--provider {provider} is not yet supported — coming soon[/red]")
        raise typer.Exit(1)


def _run_bootstrap(
    token: str,
    cluster_name: str,
    region: str,
    control_plane_url: str,
    agent_version: str,
    traefik_subnets: str,
    dns_webhook_tag: str,
    dry_run: bool,
    auto_approve: bool,
    skip_tls_verify: bool,
) -> None:
    runner.run(
        token=token,
        cluster_name=cluster_name,
        region=region,
        control_plane_url=control_plane_url,
        agent_version=agent_version,
        traefik_subnets=traefik_subnets,
        dns_webhook_tag=dns_webhook_tag,
        dry_run=dry_run,
        auto_approve=auto_approve,
        skip_tls_verify=skip_tls_verify,
    )


@app.command("connect")
def connect(
    provider: str = typer.Option(..., "--provider", "-p", help="Cloud provider (aws/gcp/azure)"),
) -> None:
    """Link a cloud account to your self-hosted cluster."""
    console.print("[yellow]Not yet implemented.[/yellow]")


@app.command("list")
def list_clusters() -> None:
    """List clusters linked to your account."""
    console.print("[yellow]Not yet implemented.[/yellow]")


@app.command("bootstrap")
def bootstrap(
    provider: str = typer.Option(
        "aws", "--provider", help="Cloud provider (aws; alicloud/gcp/azure coming soon)"
    ),
    token: str = typer.Option(
        ..., "--token", help="One-time bootstrap token from the control plane"
    ),
    cluster_name: str = typer.Option(..., "--cluster-name", help="EKS cluster name"),
    region: str = typer.Option(..., "--region", help="AWS region"),
    control_plane_url: str = typer.Option(
        CPLANE_API_URL, "--control-plane-url", help="Override the control plane API URL"
    ),
    agent_version: str = typer.Option(
        CPLANE_AGENT_DEFAULT_VERSION, "--agent-version", help="cplane-agent Helm chart version"
    ),
    traefik_subnets: str = typer.Option(
        ...,
        "--traefik-subnets",
        help="Comma-separated public subnet IDs for the Traefik NLB "
        "(get them with: aws ec2 describe-subnets "
        "--filters Name=tag:kubernetes.io/role/elb,Values=1 "
        "--query 'Subnets[].SubnetId' --output text)",
    ),
    dns_webhook_tag: str = typer.Option(
        DNS_WEBHOOK_VERSION, "--dns-webhook-tag", help="Image tag for the dns-webhook sidecar"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Print actions without executing anything"
    ),
    auto_approve: bool = typer.Option(
        False, "--auto-approve", help="Skip the interactive 'yes' confirmation prompt"
    ),
    skip_tls_verify: bool = typer.Option(
        False, "--skip-tls-verify", help="Disable TLS verification against the control plane"
    ),
) -> None:
    """Bootstrap a tenant EKS cluster: registers with the control plane, then installs
    traefik, external-dns, and the cplane-agent.

    Assumes the cluster, node group, IRSA roles (bootstrap/cluster-agent/kubeblocks),
    namespaces, and storage classes already exist — provisioned by
    terraform-cogrion-aws-eks-managed-node-group. This command only handles the
    delivery layer on top of that.
    """
    _validate_provider(provider)
    _run_bootstrap(
        token=token,
        cluster_name=cluster_name,
        region=region,
        control_plane_url=control_plane_url,
        agent_version=agent_version,
        traefik_subnets=traefik_subnets,
        dns_webhook_tag=dns_webhook_tag,
        dry_run=dry_run,
        auto_approve=auto_approve,
        skip_tls_verify=skip_tls_verify,
    )


@app.command("upgrade")
def upgrade(
    provider: str = typer.Option(
        "aws", "--provider", help="Cloud provider (aws; alicloud/gcp/azure coming soon)"
    ),
    token: str = typer.Option(
        ..., "--token", help="One-time bootstrap token from the control plane"
    ),
    cluster_name: str = typer.Option(..., "--cluster-name", help="EKS cluster name"),
    region: str = typer.Option(..., "--region", help="AWS region"),
    control_plane_url: str = typer.Option(
        CPLANE_API_URL, "--control-plane-url", help="Override the control plane API URL"
    ),
    agent_version: str = typer.Option(
        CPLANE_AGENT_DEFAULT_VERSION, "--agent-version", help="cplane-agent Helm chart version"
    ),
    traefik_subnets: str = typer.Option(
        ..., "--traefik-subnets", help="Comma-separated public subnet IDs for the Traefik NLB"
    ),
    dns_webhook_tag: str = typer.Option(
        DNS_WEBHOOK_VERSION, "--dns-webhook-tag", help="Image tag for the dns-webhook sidecar"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Print actions without executing anything"
    ),
    auto_approve: bool = typer.Option(
        True,
        "--auto-approve/--no-auto-approve",
        help="Skip the interactive 'yes' confirmation prompt",
    ),
    skip_tls_verify: bool = typer.Option(
        False, "--skip-tls-verify", help="Disable TLS verification against the control plane"
    ),
) -> None:
    """Re-apply bootstrap on an already-bootstrapped cluster to fix drift or pick up new versions.

    Runs the exact same idempotent steps as `bootstrap` — safe to re-run.
    Confirmation is skipped by default since this targets an existing cluster.
    """
    _validate_provider(provider)
    _run_bootstrap(
        token=token,
        cluster_name=cluster_name,
        region=region,
        control_plane_url=control_plane_url,
        agent_version=agent_version,
        traefik_subnets=traefik_subnets,
        dns_webhook_tag=dns_webhook_tag,
        dry_run=dry_run,
        auto_approve=auto_approve,
        skip_tls_verify=skip_tls_verify,
    )
