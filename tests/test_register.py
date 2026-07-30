import json
import subprocess

import pytest

from cogrion_cli.bootstrap import register


def _fake_completed(returncode: int, stdout: bytes = b"") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout)


def _existing_secret_json() -> bytes:
    def _b64(value: str) -> str:
        import base64

        return base64.b64encode(value.encode()).decode()

    return json.dumps(
        {
            "data": {
                "CPLANE_AGENT_UID": _b64("existing-agent-uid"),
                "CPLANE_AGENT_WORKSPACE_UID": _b64("existing-workspace-uid"),
            }
        }
    ).encode()


def test_register_agent_skips_when_secret_exists_and_not_forced(monkeypatch):
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        if cmd[:3] == ["kubectl", "get", "secret"] and "-o" not in cmd:
            return _fake_completed(0)
        if cmd[:3] == ["kubectl", "get", "secret"] and "-o" in cmd:
            return _fake_completed(0, _existing_secret_json())
        raise AssertionError(f"unexpected subprocess call: {cmd}")

    monkeypatch.setattr(register.subprocess, "run", fake_run)

    result = register.register_agent(
        control_plane_url="https://cplane.example.com",
        provider="aws",
        token="tok",
        namespace="cogrion-system",
        dry_run=False,
        force_register=False,
    )

    assert result.agent_uid == "existing-agent-uid"
    assert not any(cmd[:2] == ["kubectl", "create"] for cmd in calls if isinstance(cmd, list))


def test_register_agent_reregisters_when_secret_exists_and_forced(monkeypatch, capsys):
    def fake_run(cmd, **kwargs):
        if cmd[:3] == ["kubectl", "get", "secret"]:
            return _fake_completed(0)
        raise AssertionError(
            f"unexpected subprocess call (should not reach kubectl create in dry-run): {cmd}"
        )

    monkeypatch.setattr(register.subprocess, "run", fake_run)

    result = register.register_agent(
        control_plane_url="https://cplane.example.com",
        provider="aws",
        token="fresh-tok",
        namespace="cogrion-system",
        dry_run=True,
        force_register=True,
    )

    out = capsys.readouterr().out
    assert "re-registering" in out.lower()
    assert result.skipped is True


def test_register_agent_registers_normally_when_no_existing_secret(monkeypatch):
    def fake_run(cmd, **kwargs):
        if cmd[:3] == ["kubectl", "get", "secret"]:
            return _fake_completed(1)
        raise AssertionError(
            f"unexpected subprocess call (should not reach kubectl create in dry-run): {cmd}"
        )

    monkeypatch.setattr(register.subprocess, "run", fake_run)

    result = register.register_agent(
        control_plane_url="https://cplane.example.com",
        provider="aws",
        token="tok",
        namespace="cogrion-system",
        dry_run=True,
        force_register=False,
    )

    assert result.skipped is True
