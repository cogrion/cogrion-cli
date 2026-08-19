# Cogrion CLI

Developer CLI for the Cogrion BYOC platform — authentication, cluster linking, and deploys, in one tool.

## Install

```bash
pipx install git+https://github.com/cogrion/cogrion-cli.git@v1.0.0
```

Pin `@<tag>` to a released version — see [Releases](https://github.com/cogrion/cogrion-cli/releases) for the latest.

## Usage

```bash
cogrion auth login              # STUB
cogrion cluster connect --provider aws  # STUB
cogrion deploy run --env prod   # STUB
```

> **STUB** — the three commands above are scaffolding only and do not yet do anything.

`cogrion cluster bootstrap` and `cogrion cluster upgrade` are implemented and handle the delivery layer on top of an already-provisioned cluster: registration with the control plane, external-dns, KubeBlocks, and the `cplane-agent`. They assume the cluster and its underlying infrastructure already exist — provisioned by Terraform, which also runs this exact command in-cluster by default as part of its own bootstrap process.

```bash
cogrion cluster bootstrap \
  --provider aws \
  --token <bootstrap-token> \
  --cluster-name <cluster-name> \
  --region ap-southeast-1 \
  --control-plane-url https://cplane.api.cogrion.com \
  --tofu-backend-bucket <bucket-for-tofu-state>

# re-apply on an already-bootstrapped cluster to fix drift or pick up new versions
cogrion cluster upgrade \
  --provider aws \
  --token <bootstrap-token> \
  --cluster-name <cluster-name> \
  --region ap-southeast-1 \
  --tofu-backend-bucket <bucket-for-tofu-state>
```

`--control-plane-url` defaults to `https://cplane.api.cogrion.com` — override it if your cluster's control plane lives on a region-specific deployment (e.g. `https://cplane-api.sgp.prod.cogrion.com`).

Both accept `--dry-run` to preview every action with no cloud/kubectl/helm calls made.

`upgrade` skips registration and the addon reconcile by default once a cluster is already bootstrapped. Two escape hatches when you need to force it anyway:

- `--force-register` — re-registers with the control plane using a fresh one-time `--token`, overwriting the existing `cluster-agent-credentials` secret. Use this to rotate mTLS credentials (e.g. after the agent starts failing its sync heartbeat with `403`).
- `--force-upgrade` — re-runs the KubeBlocks CRD re-apply, Helm upgrade, and rollout restart for every addon even if already at the target version.

`--agent-service-account-name` (default `cplane-agent`) sets the pre-provisioned ServiceAccount the `cplane-agent` release runs as — override it if your cluster's IRSA/RRSA setup uses a different name.

`--agent-replica-count` (default `2`) sets the number of `cplane-agent` pod replicas.

Select the target with `--provider` (or the `COGRION_PROVIDER` environment variable), default `aws`:

| Provider | Status |
|---|---|
| AWS | Supported |
| Alicloud | Supported |
| GCP | Not yet supported |
| Azure | Not yet supported |

Make sure the right cloud credentials are active in your shell before running either command (e.g. `AWS_PROFILE` for AWS, `aliyun configure` for Alicloud) — otherwise both fail with `Could not discover this cluster's OIDC issuer`.

## Development

```bash
pipx install --editable .
```

Editable install picks up local code changes without reinstalling — restart your shell (or `hash -r`) if `cogrion` doesn't reflect a change.

```bash
make install
make test
make lint
```

### Releasing

Version bumps and tags are separate PRs from the feature/fix work — the tag is what `pipx install ...@<tag>` above pins to.

```bash
# 1. Bump on a release branch, PR it, get it merged to main
make bump-patch   # or bump-minor / bump-major
cat VERSION       # confirm the new version, e.g. 1.1.0
git checkout -b chore/release-1.1.0
git add pyproject.toml VERSION CHANGELOG.md
git commit -m "Release 1.1.0"
git push -u origin chore/release-1.1.0
# open PR, get it reviewed and merged into main

# 2. Once the bump is merged, tag that commit on main and push the tag
git checkout main
git pull
git tag v1.1.0
git push origin v1.1.0
```

See [AGENTS.md](AGENTS.md) for repo conventions.
