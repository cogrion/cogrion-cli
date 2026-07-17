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
    providers/
      base.py       # BaseProvider ABC
      aws/          # AWSProvider — IRSA roles only (bootstrap, cluster-agent);
                     # node group/security group/kubeblocks stay Terraform's job
        iam/         # IAM policy JSON, bundled into the wheel
```

## During development

- Install with `pipx install --editable .`
- Editable install reflects local code changes immediately; no reinstall needed after editing a command

## Conventions

- No comments unless the WHY is non-obvious
- Sub-apps live under `commands/`, one file per top-level noun (`auth`, `cluster`, `deploy`) — do not put unrelated commands in an existing file
- Every command must respect the global `--json` flag once it has real output — no `rich` formatting when `state.json_output` is set
- Session/auth state goes through `config.py`'s `app_dir()`, never a hardcoded path
- Version bumps: `make bump-patch` / `make bump-minor` / `make bump-major` — never edit `VERSION` or `pyproject.toml` by hand
- `bootstrap/` deliberately does not touch: node group creation, security groups, launch templates (owned by `terraform-workspace-infra-aws`), or the KubeBlocks operator itself (installed later by `cplane-agent`'s KCL stacks) — only its IRSA role/namespace/service-accounts live in Terraform too, not here
- Every `--dry-run` path in `bootstrap/` must be fully offline — no real AWS/kubectl/helm calls, not even read-only ones — so it can be exercised without live credentials
