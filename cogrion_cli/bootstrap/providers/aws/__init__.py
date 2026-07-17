import json
import os
import re
import subprocess

import boto3

from ...addons import HelmAddon, make_traefik
from ..base import BaseProvider

_POLICY_DIR = os.path.join(os.path.dirname(__file__), "iam")

# Maps role key -> (policy file, format vars, trusted service accounts).
# kubeblocks, cluster-autoscaler, efs-csi-driver, alb-controller, and
# external-secrets IRSA roles are intentionally not here — they're either
# Terraform's job (kubeblocks, via terraform-workspace-infra-aws) or out of
# scope for this minimal bootstrap (the rest).
_IRSA_ROLES = {
    "bootstrap": (
        "bootstrap.json",
        ["ext_workspace_id", "aws_account_id"],
        ["cogrion-system:bootstrap-sa"],
    ),
    "cluster-agent": (
        "cluster-agent.json",
        ["ext_workspace_id", "aws_account_id", "ext_account_id"],
        ["cogrion-system:cplane-agent"],
    ),
}


class AWSProvider(BaseProvider):
    def __init__(
        self,
        ext_account_id: str,
        ext_workspace_id: str,
        cluster_name: str,
        region: str,
        dry_run: bool,
    ):
        super().__init__(
            ext_account_id=ext_account_id,
            ext_workspace_id=ext_workspace_id,
            cluster_name=cluster_name,
            dry_run=dry_run,
        )
        self.region = region
        self.eks = boto3.client("eks", region_name=region)
        self.iam = boto3.client("iam")
        self.sts = boto3.client("sts")
        self._cached_oidc_arn: str = ""
        self._cached_oidc_url: str = ""
        self._cached_account_id: str = ""

    def addons(self, traefik_subnets: str = "", node_selector_set: dict | None = None) -> list[HelmAddon]:
        return [make_traefik(traefik_subnets)]

    def ensure_iam(self) -> dict[str, str]:
        """Create the bootstrap and cluster-agent IRSA roles and their k8s ServiceAccounts.

        Returns a map of role-key -> IAM role ARN.
        """
        ext_workspace_id = self.ext_workspace_id or "<ext-workspace-id>"

        if self.dry_run:
            arns: dict[str, str] = {}
            for role_key, (_, __, service_accounts) in _IRSA_ROLES.items():
                role_name = f"{ext_workspace_id}-{role_key}-role"
                print(
                    f"[aws] dry-run: would ensure IRSA role '{role_name}' "
                    f"for {service_accounts}"
                )
                arns[role_key] = f"arn:aws:iam::000000000000:role/{role_name}"
            return arns

        aws_account_id = self._get_account_id()
        format_vars = {
            "ext_workspace_id": ext_workspace_id,
            "aws_account_id": aws_account_id,
            "ext_account_id": self.ext_account_id,
        }

        arns: dict[str, str] = {}
        for role_key, (policy_file, var_keys, service_accounts) in _IRSA_ROLES.items():
            role_name = f"{ext_workspace_id}-{role_key}-role"
            policy_name = f"{ext_workspace_id}-{role_key}-policy"
            vars_for_policy = {k: format_vars[k] for k in var_keys}
            policy_doc = _load_policy(policy_file, **vars_for_policy)
            arn = self._ensure_irsa_role(
                role_name=role_name,
                policy_name=policy_name,
                policy_doc=policy_doc,
                service_accounts=service_accounts,
            )
            arns[role_key] = arn
            for ns_sa in service_accounts:
                namespace, sa_name = ns_sa.split(":", 1)
                self._ensure_service_account(namespace=namespace, name=sa_name, role_arn=arn)

        return arns

    def _ensure_service_account(self, namespace: str, name: str, role_arn: str) -> None:
        """Idempotently create a k8s ServiceAccount annotated with the IRSA role ARN."""
        check = subprocess.run(
            ["kubectl", "get", "serviceaccount", name, "-n", namespace],
            capture_output=True,
        )
        if check.returncode == 0:
            print(f"[aws] ServiceAccount {namespace}/{name} exists — patching annotation")
            if not self.dry_run:
                subprocess.run(
                    [
                        "kubectl",
                        "annotate",
                        "serviceaccount",
                        name,
                        "-n",
                        namespace,
                        f"eks.amazonaws.com/role-arn={role_arn}",
                        "--overwrite",
                    ],
                    check=True,
                )
            return

        print(f"[aws] creating ServiceAccount {namespace}/{name}")
        if self.dry_run:
            print(f"[aws] dry-run: skipping ServiceAccount creation")
            return

        subprocess.run(
            ["kubectl", "apply", "-f", "-"],
            input=subprocess.run(
                ["kubectl", "create", "namespace", namespace, "--dry-run=client", "-o", "yaml"],
                capture_output=True,
                check=True,
            ).stdout,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["kubectl", "apply", "-f", "-"],
            input=subprocess.run(
                [
                    "kubectl",
                    "create",
                    "serviceaccount",
                    name,
                    "-n",
                    namespace,
                    "--dry-run=client",
                    "-o",
                    "yaml",
                ],
                capture_output=True,
                check=True,
            ).stdout,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            [
                "kubectl",
                "annotate",
                "serviceaccount",
                name,
                "-n",
                namespace,
                f"eks.amazonaws.com/role-arn={role_arn}",
                "--overwrite",
            ],
            check=True,
        )
        print(f"[aws] ServiceAccount {namespace}/{name} created")

    def _get_account_id(self) -> str:
        if not self._cached_account_id:
            self._cached_account_id = self.sts.get_caller_identity()["Account"]
        return self._cached_account_id

    def _get_oidc(self) -> tuple[str, str]:
        """Return (oidc_provider_arn, oidc_url_without_scheme) for the cluster."""
        if self._cached_oidc_arn:
            return self._cached_oidc_arn, self._cached_oidc_url

        cluster = self.eks.describe_cluster(name=self.cluster_name)
        issuer = cluster["cluster"]["identity"]["oidc"]["issuer"]
        oidc_url = issuer.replace("https://", "")

        aws_account_id = self._get_account_id()
        region = self.region
        oidc_id = oidc_url.split("/")[-1]
        arn = f"arn:aws:iam::{aws_account_id}:oidc-provider/oidc.eks.{region}.amazonaws.com/id/{oidc_id}"

        self._cached_oidc_arn = arn
        self._cached_oidc_url = oidc_url
        return arn, oidc_url

    def _ensure_irsa_role(
        self,
        role_name: str,
        policy_name: str,
        policy_doc: str,
        service_accounts: list[str],
    ) -> str:
        """Idempotently create an IRSA role and return its ARN."""
        oidc_arn, oidc_url = self._get_oidc()
        subjects = [f"system:serviceaccount:{sa}" for sa in service_accounts]
        trust = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"Federated": oidc_arn},
                    "Action": "sts:AssumeRoleWithWebIdentity",
                    "Condition": {
                        "StringEquals": {
                            f"{oidc_url}:sub": subjects,
                            f"{oidc_url}:aud": "sts.amazonaws.com",
                        }
                    },
                }
            ],
        }

        try:
            arn = self.iam.get_role(RoleName=role_name)["Role"]["Arn"]
            role_exists = True
            print(f"[aws] IRSA role '{role_name}' exists — updating trust policy")
        except self.iam.exceptions.NoSuchEntityException:
            role_exists = False
            arn = f"arn:aws:iam::000000000000:role/{role_name}"

        if self.dry_run:
            print(f"[aws] dry-run: skipping IRSA role/policy changes for '{role_name}'")
            return arn

        # _ensure_policy runs regardless of whether the role already exists —
        # an existing role does not imply its attached policy document is
        # still up to date (e.g. after editing providers/aws/iam/*.json).
        if role_exists:
            self.iam.update_assume_role_policy(
                RoleName=role_name,
                PolicyDocument=json.dumps(trust),
            )
        else:
            print(f"[aws] creating IRSA role '{role_name}'")

        policy_arn = self._ensure_policy(policy_name, policy_doc)

        if not role_exists:
            arn = self.iam.create_role(
                RoleName=role_name,
                AssumeRolePolicyDocument=json.dumps(trust),
            )["Role"]["Arn"]
            print(f"[aws] IRSA role created: {arn}")

        self.iam.attach_role_policy(RoleName=role_name, PolicyArn=policy_arn)
        return arn

    def _ensure_policy(self, policy_name: str, policy_doc: str) -> str:
        """Idempotently create a customer-managed policy and return its ARN.

        If the policy already exists, its current default version is compared
        against `policy_doc` and a new version is pushed only when they
        differ — a resolved-but-unchanged document (e.g. same placeholders,
        different key order) must not create a spurious version, since IAM
        caps managed policies at 5 versions.
        """
        aws_account_id = self._get_account_id()
        policy_arn = f"arn:aws:iam::{aws_account_id}:policy/{policy_name}"
        try:
            policy = self.iam.get_policy(PolicyArn=policy_arn)["Policy"]
        except self.iam.exceptions.NoSuchEntityException:
            print(f"[aws] creating IAM policy '{policy_name}'")
            self.iam.create_policy(PolicyName=policy_name, PolicyDocument=policy_doc)
            return policy_arn

        current_doc = self.iam.get_policy_version(
            PolicyArn=policy_arn, VersionId=policy["DefaultVersionId"]
        )["PolicyVersion"]["Document"]

        if current_doc == json.loads(policy_doc):
            print(f"[aws] IAM policy '{policy_name}' already up to date")
            return policy_arn

        print(f"[aws] IAM policy '{policy_name}' exists but changed — pushing new version")
        self._prune_oldest_policy_version_if_at_limit(policy_arn)
        self.iam.create_policy_version(
            PolicyArn=policy_arn, PolicyDocument=policy_doc, SetAsDefault=True
        )
        return policy_arn

    def _prune_oldest_policy_version_if_at_limit(self, policy_arn: str) -> None:
        """IAM allows at most 5 versions per managed policy. Delete the oldest
        non-default version before pushing a new one if already at the cap."""
        versions = self.iam.list_policy_versions(PolicyArn=policy_arn)["Versions"]
        if len(versions) < 5:
            return
        oldest = min(
            (v for v in versions if not v["IsDefaultVersion"]),
            key=lambda v: v["CreateDate"],
        )
        print(f"[aws] policy at 5-version limit — deleting oldest version {oldest['VersionId']}")
        self.iam.delete_policy_version(PolicyArn=policy_arn, VersionId=oldest["VersionId"])


def _load_policy(filename: str, **vars) -> str:
    path = os.path.normpath(os.path.join(_POLICY_DIR, filename))
    with open(path) as f:
        content = f.read()
    for key, value in vars.items():
        content = content.replace("{" + key + "}", value)
    unresolved = re.findall(r"\{[a-zA-Z_][a-zA-Z0-9_]*\}", content)
    if unresolved:
        raise ValueError(f"Unresolved placeholders in {filename}: {unresolved}")
    json.loads(content)  # validate structure
    return content
