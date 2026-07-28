# Cogrion CLI

Developer CLI for the Cogrion BYOC platform — authentication, cluster linking, and deploys, in one tool.

## Install

```bash
pipx install --editable .
```

Editable install picks up local code changes without reinstalling — restart your shell (or `hash -r`) if `cogrion` doesn't reflect a change.

## Usage

```bash
cogrion auth login              # STUB
cogrion cluster connect --provider aws  # STUB
cogrion deploy run --env prod   # STUB
```

> **STUB** — the three commands above are scaffolding only and do not yet do anything.

`cogrion cluster bootstrap` and `cogrion cluster upgrade` are implemented and handle the delivery layer on top of an already-provisioned cluster: registration with the control plane, external-dns, KubeBlocks, and the `cplane-agent`. They assume the cluster, node group, IRSA roles, namespaces, storage classes, and traefik already exist — provisioned by Terraform, which also runs this exact command in-cluster by default as part of its own bootstrap process:

```bash
cogrion cluster bootstrap \
  --token <bootstrap-token> \
  --cluster-name <eks-cluster-name> \
  --region ap-southeast-1 \
  --control-plane-url https://cplane.api.cogrion.com \
  --tofu-backend-bucket <s3-bucket-for-tofu-state>

# re-apply on an already-bootstrapped cluster to fix drift or pick up new versions
cogrion cluster upgrade \
  --token <bootstrap-token> \
  --cluster-name <eks-cluster-name> \
  --region ap-southeast-1 \
  --tofu-backend-bucket <s3-bucket-for-tofu-state>
```

`--control-plane-url` defaults to `https://cplane.api.cogrion.com` — override it if your cluster's control plane lives on a region-specific deployment (e.g. `https://cplane-api.sgp.prod.cogrion.com`).

Both accept `--dry-run` to preview every action with no AWS/kubectl/helm calls made.

`upgrade` skips registration and the addon reconcile by default once a cluster is already bootstrapped. Two escape hatches when you need to force it anyway:

- `--force-register` — re-registers with the control plane using a fresh one-time `--token`, overwriting the existing `cluster-agent-credentials` secret. Use this to rotate mTLS credentials (e.g. after the agent starts failing its sync heartbeat with `403`).
- `--force-upgrade` — re-runs the KubeBlocks CRD re-apply, Helm upgrade, and rollout restart for every addon even if already at the target version.

### AWS credentials

When run outside a cluster (i.e. from your own machine, not the in-cluster bootstrap Job), both commands shell out to `aws eks describe-cluster` to discover the cluster's OIDC issuer. This call has no `--profile` flag of its own — it relies entirely on ambient AWS credentials in your shell. Make sure the right profile is active first:

```bash
export AWS_PROFILE=<profile-with-access-to-the-target-cluster>
```

Without this, both commands fail with `Could not discover this cluster's OIDC issuer` even though the token and cluster name are correct.

Select the target with `--provider` (default `aws`):

| Provider | Status | What `bootstrap`/`upgrade` does |
|---|---|---|
| AWS | Supported | Verifies `cogrion-system` namespace exists, registers with the control plane, installs external-dns + dns-webhook, KubeBlocks (+ snapshot-controller CRDs and its S3 backup bucket), and the `cplane-agent` Helm release |
| AliCloud | Not yet supported | — |
| GCP | Not yet supported | — |
| Azure | Not yet supported | — |

## Development

```bash
make install
make test
make lint
```

See [AGENTS.md](AGENTS.md) for repo conventions.
