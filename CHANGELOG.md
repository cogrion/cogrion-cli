# Changelog

## Unreleased

- Fix `cluster bootstrap`/`upgrade` failing on `BucketAlreadyOwnedByYou` when the KubeBlocks backup bucket already exists: `head-bucket` now checks the target region (it previously checked the CLI's default region, so an existing bucket in another region went undetected) and `create-bucket` treats `BucketAlreadyOwnedByYou` as a successful adopt instead of raising. Logs now say `created` or `already exists — adopting`.
- After installing KubeBlocks, `kubectl rollout restart` (and wait for healthy) `deployment/kubeblocks` and `deployment/kubeblocks-dataprotection` in `kb-system` — the old `bootstrap.sh` had this commented out; now live for both deployments.
- Install KubeBlocks (+ snapshot-controller CRDs, backup S3 bucket) as part of `cluster bootstrap`/`upgrade` — the old `bootstrap.sh` did this but it was dropped in the port to cogrion-cli and nothing replaced it. Add required `--tofu-backend-bucket` and optional `--tofu-backend-region`/`--kubeblocks-backup-bucket`/`--kubeblocks-backup-region`; set `tofu.backendBucket`/`tofu.backendRegion`/`aws.region` on the `cplane-agent` install (it was crash-looping on a missing `TOFU_BACKEND_BUCKET` env var).
- Rescope `cogrion cluster bootstrap`/`upgrade` to delivery-only: drop all AWS SDK (boto3) usage and IRSA-role/namespace creation, now owned by Terraform. The commands preflight-check that `cogrion-system` exists (failing clearly if not) instead of creating it, and install traefik/external-dns/`cplane-agent` on top. Add `--provider` (default `aws`, validated).
- Add `cogrion cluster bootstrap` / `cogrion cluster upgrade`: provisions IRSA roles (bootstrap, cluster-agent), traefik, external-dns (+dns-webhook), and the `cplane-agent`, ported from `cogrion-bootstrap` and trimmed to what isn't already owned by Terraform or `cplane-agent`'s KCL stacks.

## 0.1.0

- Initial scaffold: `auth`, `cluster`, `deploy` command groups (stubs), global `--json` flag, graceful Ctrl+C handling.
