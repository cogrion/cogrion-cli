# Changelog

## Unreleased

- Rescope `cogrion cluster bootstrap`/`upgrade` to delivery-only: drop all AWS SDK (boto3) usage and IRSA-role/namespace creation, now owned by Terraform. The commands preflight-check that `cogrion-system` exists (failing clearly if not) instead of creating it, and install traefik/external-dns/`cplane-agent` on top. Add `--provider` (default `aws`, validated).
- Add `cogrion cluster bootstrap` / `cogrion cluster upgrade`: provisions IRSA roles (bootstrap, cluster-agent), traefik, external-dns (+dns-webhook), and the `cplane-agent`, ported from `cogrion-bootstrap` and trimmed to what isn't already owned by Terraform or `cplane-agent`'s KCL stacks.

## 0.1.0

- Initial scaffold: `auth`, `cluster`, `deploy` command groups (stubs), global `--json` flag, graceful Ctrl+C handling.
