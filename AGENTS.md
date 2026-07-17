# Agent context — cogrion-cli

## What this repo is

The developer-facing CLI for the Cogrion BYOC platform: authentication, cluster linking, and deploys. Intended to eventually absorb what `cogrion-bootstrap` does today, wrapped in a single cohesive `cogrion` command instead of a standalone bootstrap script.

## Layout

```
cogrion_cli/
  cli.py            # Typer root app, global --json flag, KeyboardInterrupt handling
  config.py         # app_dir()/config_file() — session state under typer.get_app_dir()
  state.py          # shared State dataclass (json_output flag, etc.)
  commands/
    auth.py         # `cogrion auth ...`
    cluster.py      # `cogrion cluster ...` — includes bootstrap/upgrade, wired to bootstrap/
    deploy.py       # `cogrion deploy ...`
  bootstrap/        # tenant cluster bootstrap — ported from cogrion-bootstrap, trimmed
    runner.py       # orchestrates the full bootstrap/upgrade flow
    register.py     # POST /agent/register → writes cluster-agent-credentials secret
    helm.py         # helm_apply() with stuck-release handling — the only place that shells out to helm
    addons.py       # traefik + external-dns(+dns-webhook) HelmAddon definitions
```

No AWS SDK (boto3) anywhere in this package — `bootstrap/` makes zero AWS API calls. IRSA roles, namespaces, service accounts, and storage classes are entirely `terraform-cogrion-aws-eks-managed-node-group`'s job; this package only does registration + Helm installs on top of what Terraform already provisioned. It's invoked two ways: a human running `cogrion cluster bootstrap` directly, or that same Terraform module's `tenant_bootstrap`-gated Job running it in-cluster via the `bootstrap-sa` IRSA identity — same command either way, just a different trigger.

## During development

- Install with `pipx install --editable .`
- Editable install reflects local code changes immediately; no reinstall needed after editing a command

## Conventions

- No comments unless the WHY is non-obvious
- Sub-apps live under `commands/`, one file per top-level noun (`auth`, `cluster`, `deploy`) — do not put unrelated commands in an existing file
- Every command must respect the global `--json` flag once it has real output — no `rich` formatting when `state.json_output` is set
- Session/auth state goes through `config.py`'s `app_dir()`, never a hardcoded path
- Version bumps: `make bump-patch` / `make bump-minor` / `make bump-major` — never edit `VERSION` or `pyproject.toml` by hand
- `bootstrap/` deliberately does not touch: node group creation, IRSA roles, namespaces, storage classes (owned by `terraform-cogrion-aws-eks-managed-node-group`), or the KubeBlocks operator itself (installed later by `cplane-agent`'s KCL stacks) — it only preflight-checks that `cogrion-system` exists and fails clearly if it doesn't
- Every `--dry-run` path in `bootstrap/` must be fully offline — no real AWS/kubectl/helm calls, not even read-only ones — so it can be exercised without live credentials
