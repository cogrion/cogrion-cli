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
    addons.py       # external-dns(+dns-webhook) + kubeblocks HelmAddon definitions
```

No cloud SDKs (boto3, aliyun-python-sdk, ...) anywhere in this package — `bootstrap/` makes zero cloud API calls directly, only shelling out to each cloud's own CLI (`aws`, `aliyun`) via `subprocess`. IRSA/RRSA roles, namespaces, service accounts, and storage classes are entirely the relevant `terraform-cogrion-*-managed-*` module's job; this package only does registration + Helm installs on top of what Terraform already provisioned. It's invoked two ways: a human running `cogrion cluster bootstrap` directly, or that same Terraform module's `tenant_bootstrap`-gated Job running it in-cluster via the workload-identity (IRSA/RRSA) SA — same command either way, just a different trigger.

`bootstrap/` supports multiple clouds via an explicit, required `provider` parameter ("aws" or "alicloud") threaded through every function that branches on it (`runner.run`, `register_agent`, `_discover_oidc_issuer`, `_ensure_backup_bucket`, `make_kubeblocks`) — no function defaults silently to "aws". Only `commands/cluster.py`'s `--provider`/`COGRION_PROVIDER` CLI option carries a default. Adding a cloud means adding an `elif provider == "..."` branch (raising `ValueError` on anything else) in each of those functions, not a new code path elsewhere.

## During development

- Install with `pipx install --editable .`
- Editable install reflects local code changes immediately; no reinstall needed after editing a command

## Conventions

- No comments unless the WHY is non-obvious
- Sub-apps live under `commands/`, one file per top-level noun (`auth`, `cluster`, `deploy`) — do not put unrelated commands in an existing file
- Every command must respect the global `--json` flag once it has real output — no `rich` formatting when `state.json_output` is set
- Session/auth state goes through `config.py`'s `app_dir()`, never a hardcoded path
- Version bumps: `make bump-patch` / `make bump-minor` / `make bump-major` — never edit `VERSION` or `pyproject.toml` by hand
- `bootstrap/` deliberately does not touch: node group creation, IRSA/RRSA roles, namespaces, storage classes (owned by each provider's `terraform-cogrion-*-managed-*` module) — it only preflight-checks that `cogrion-system` exists and fails clearly if it doesn't
- It does install the KubeBlocks operator itself (+ snapshot-controller CRDs, backup bucket — S3 on AWS, OSS on Alicloud) — the Terraform module only pre-provisions `kb-system`'s namespace/workload-identity/ServiceAccounts, not the operator
- Every `--dry-run` path in `bootstrap/` must be fully offline — no real cloud/kubectl/helm calls, not even read-only ones — so it can be exercised without live credentials
