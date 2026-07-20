import json
import subprocess

from cogrion_cli.bootstrap import helm


def test_ensure_helm_repos_updates_only_the_requested_repos(monkeypatch):
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        if cmd[:3] == ["helm", "repo", "list"]:
            return subprocess.CompletedProcess(
                args=cmd,
                returncode=0,
                stdout=json.dumps(
                    [
                        {"name": "traefik", "url": "https://traefik.github.io/charts"},
                        {"name": "karpenter", "url": "https://karpenter.example.com"},
                        {"name": "crossview", "url": "https://corpobit.github.io/crossview"},
                    ]
                ),
            )
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(helm.subprocess, "run", fake_run)

    helm.ensure_helm_repos({"traefik": "https://traefik.github.io/charts"}, dry_run=False)

    update_calls = [c for c in calls if c[:2] == ["helm", "repo"] and "update" in c]
    assert len(update_calls) == 1
    update_cmd = update_calls[0]

    # Must target only the repo(s) this run actually needs — not every repo
    # configured on the operator's machine (which, in production, includes
    # dozens of unrelated repos and can include ones that 404).
    assert update_cmd == ["helm", "repo", "update", "traefik"]
