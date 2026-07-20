import json
import subprocess
import tempfile
import os

from .addons import HelmAddon


def is_externally_managed(kind: str, name: str, namespace: str) -> bool:
    """Return True if the resource exists but is not managed by Helm."""
    result = subprocess.run(
        [
            "kubectl",
            "get",
            kind,
            name,
            "-n",
            namespace,
            "-o",
            "jsonpath={.metadata.labels.app\\.kubernetes\\.io/managed-by}",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return False  # resource does not exist
    managed_by = result.stdout.strip()
    return managed_by != "Helm"


def _helm_status(release: str, namespace: str) -> str:
    result = subprocess.run(
        ["helm", "status", release, "-n", namespace, "-o", "json"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return ""
    try:
        return json.loads(result.stdout).get("info", {}).get("status", "")
    except Exception:
        return ""


def installed_chart(release: str, namespace: str) -> tuple[str, str]:
    """The (chart name, chart version) currently deployed for this release,
    or ("", "") if the release doesn't exist. Used to decide whether an
    upgrade actually has anything to do — comparing kubectl/helm's own
    free-text stdout for "unchanged" is unreliable (server-side apply in
    particular doesn't consistently report it), so we compare the
    source-of-truth chart identity instead.

    Uses `helm get metadata`, not `helm status` — `helm status -o json` on
    Helm v3.18.6 has no "chart" key at all (verified against a live
    cluster), so anything relying on it always fell through to ("", "").
    `helm get metadata` returns "chart" and "version" as clean top-level
    fields."""
    result = subprocess.run(
        ["helm", "get", "metadata", release, "-n", namespace, "-o", "json"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return "", ""
    try:
        data = json.loads(result.stdout)
        return data.get("chart", ""), data.get("version", "")
    except Exception:
        return "", ""


def needs_upgrade(addon: HelmAddon) -> bool:
    """True if `addon` isn't installed yet, targets a different chart than
    what's currently deployed under this release name, or the installed
    version differs from `addon.version`. Checking chart name as well as
    version — not version alone — matters because a release name is only
    unique within a namespace: if it were ever repointed at a different
    chart, a coincidentally-matching version string would wrongly look
    up to date. Reusable by any caller that wants to skip disruptive
    follow-up work (CRD re-apply, forced restarts, ...) when a re-run of an
    already-current addon has nothing to do.

    Version comparison strips a leading "v" from both sides before
    comparing: some addons (e.g. kubeblocks) reuse a GitHub release tag
    like "v1.0.2" as both the CRD download path and the Helm --version flag,
    but Helm's own semver handling normalizes that prefix away internally,
    so `helm status`'s recorded chart version can come back as "1.0.2" for
    an install that was actually given "v1.0.2" — a naive exact-string
    comparison would see that as a permanent mismatch and never recognize
    the addon as up to date."""
    installed_name, installed_version = installed_chart(addon.release_name, addon.namespace)
    target_name = addon.chart.rsplit("/", 1)[-1]
    return (installed_name, installed_version.lstrip("v")) != (
        target_name,
        addon.version.lstrip("v"),
    )


def _helm_description(release: str, namespace: str) -> str:
    """The reason for the release's current status, e.g. why it failed."""
    result = subprocess.run(
        ["helm", "status", release, "-n", namespace, "-o", "json"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return ""
    try:
        return json.loads(result.stdout).get("info", {}).get("description", "")
    except Exception:
        return ""


def ensure_helm_repos(repos: dict[str, str], dry_run: bool = False) -> None:
    for name, url in repos.items():
        result = subprocess.run(
            ["helm", "repo", "list", "-o", "json"],
            capture_output=True,
            text=True,
        )
        existing = []
        try:
            existing = [r["name"] for r in json.loads(result.stdout or "[]")]
        except Exception:
            pass

        if name in existing:
            print(f"[helm] repo '{name}' already added — skipping")
            continue

        print(f"[helm] adding repo '{name}' ({url})")
        if not dry_run:
            subprocess.run(["helm", "repo", "add", name, url], check=True)

    if not dry_run and repos:
        # Only the repos this run actually needs — the operator's machine
        # commonly has dozens of unrelated repos configured (and some of
        # those can 404), so `helm repo update` with no args is both slow
        # and needlessly fragile.
        subprocess.run(["helm", "repo", "update", *repos.keys()], check=True)


def helm_apply(
    release: str,
    namespace: str,
    chart: str,
    version: str | None = None,
    set_args: dict | None = None,
    values_yaml: str = "",
    dry_run: bool = False,
) -> None:
    status = _helm_status(release, namespace)
    print(f"[helm] {release} current status: {status or 'not found'}")

    if status in ("pending-install", "pending-upgrade", "pending-rollback", "failed"):
        # A "failed" release has no guarantee of a prior successfully-deployed
        # revision to roll back to — often the failure IS revision 1, in which
        # case `helm rollback` (no target) errors with "release has no 0
        # version" and leaves the broken history in place. Delete-and-reinstall
        # is the only recovery that works unconditionally.
        reason = _helm_description(release, namespace)
        suffix = f": {reason}" if reason else ""
        print(f"[helm] {release} stuck in '{status}'{suffix} — deleting before reinstall")
        if not dry_run:
            subprocess.run(["helm", "delete", release, "-n", namespace], check=False)

    cmd = [
        "helm",
        "upgrade",
        "--install",
        release,
        chart,
        "--namespace",
        namespace,
        "--create-namespace",
        "--timeout",
        "600s",
        "--wait",
    ]

    if version:
        cmd += ["--version", version]

    for key, value in (set_args or {}).items():
        if value:
            escaped = str(value).replace(",", "\\,")
            cmd += ["--set", f"{key}={escaped}"]

    tmp_values = None
    if values_yaml:
        tmp_values = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False)
        tmp_values.write(values_yaml)
        tmp_values.flush()
        cmd += ["--values", tmp_values.name]

    print(f"[helm] running: {' '.join(cmd)}")

    if dry_run:
        if tmp_values:
            os.unlink(tmp_values.name)
        print(f"[helm] dry-run: skipping execution")
        return

    result = subprocess.run(cmd, capture_output=True, text=True)
    if tmp_values:
        os.unlink(tmp_values.name)
    if result.returncode != 0:
        stderr = result.stderr.strip()
        if (
            "cannot be imported into the current release" in stderr
            and "invalid ownership metadata" in stderr
        ):
            print(f"[helm] {release} already managed outside Helm — skipping")
            return
        error_detail = stderr or result.stdout.strip()
        raise RuntimeError(
            f"[helm] '{release}' install failed (exit {result.returncode}):\n{error_detail}"
        )

    print(f"[helm] {release} ready")
