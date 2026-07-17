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

`cogrion cluster bootstrap` and `cogrion cluster upgrade` are implemented and handle the delivery layer on top of an already-provisioned cluster: registration with the control plane, traefik, external-dns, and the `cplane-agent`. They assume the cluster, node group, IRSA roles, namespaces, and storage classes already exist — provisioned by Terraform, which also runs this exact command in-cluster by default as part of its own bootstrap process:

```bash
cogrion cluster bootstrap \
  --token <bootstrap-token> \
  --cluster-name <eks-cluster-name> \
  --region ap-southeast-1 \
  --traefik-subnets subnet-aaa111,subnet-bbb222 \
  --control-plane-url https://cplane.api.cogrion.com

# re-apply on an already-bootstrapped cluster to fix drift or pick up new versions
cogrion cluster upgrade --token <bootstrap-token> --cluster-name <eks-cluster-name> --region ap-southeast-1 --traefik-subnets subnet-aaa111,subnet-bbb222
```

Both accept `--dry-run` to preview every action with no AWS/kubectl/helm calls made.

Select the target with `--provider` (default `aws`):

| Provider | Status | What `bootstrap`/`upgrade` does |
|---|---|---|
| AWS | Supported | Verifies `cogrion-system` namespace exists, registers with the control plane, installs traefik, external-dns + dns-webhook, and the `cplane-agent` Helm release |
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
