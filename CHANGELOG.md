# Changelog

## Unreleased

- Add `cogrion cluster bootstrap` / `cogrion cluster upgrade`: provisions IRSA roles (bootstrap, cluster-agent), traefik, external-dns (+dns-webhook), and the `cplane-agent`, ported from `cogrion-bootstrap` and trimmed to what isn't already owned by Terraform or `cplane-agent`'s KCL stacks.

## 0.1.0

- Initial scaffold: `auth`, `cluster`, `deploy` command groups (stubs), global `--json` flag, graceful Ctrl+C handling.
