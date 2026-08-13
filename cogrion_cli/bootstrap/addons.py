from dataclasses import dataclass, field


@dataclass
class HelmAddon:
    release_name: str
    namespace: str
    chart: str
    version: str = ""
    repo_name: str | None = None
    repo_url: str | None = None
    set_args: dict = field(default_factory=dict)
    values_yaml: str = ""
    detect: tuple[str, str] | None = None


DNS_WEBHOOK_IMAGE = "harbor.sgp.prod.cogrion.com/public-ecr-proxy/quantdata/cogrion/dns-webhook"
DNS_WEBHOOK_VERSION = "0.1.6"

# external-dns with the dns-webhook sidecar. The sidecar proxies the
# external-dns webhook provider protocol to the control-plane, which holds the
# Cloudflare token — it never reaches the tenant cluster.
_CREDENTIALS_SECRET = "cluster-agent-credentials"

_EXTERNAL_DNS_VALUES_TEMPLATE = """\
provider:
  name: webhook
  webhook:
    image:
      repository: {image}
      tag: "{tag}"
    env:
      - name: CONTROL_PLANE_URL
        value: "{control_plane_url}"
      - name: PORT
        value: "8888"
      - name: MTLS_CLIENT_CERT
        valueFrom:
          secretKeyRef:
            name: {secret}
            key: CPLANE_AGENT_MTLS_CLIENT_CERT
      - name: MTLS_CLIENT_KEY
        valueFrom:
          secretKeyRef:
            name: {secret}
            key: CPLANE_AGENT_MTLS_CLIENT_KEY
      - name: MTLS_CA_CERT
        valueFrom:
          secretKeyRef:
            name: {secret}
            key: CPLANE_AGENT_MTLS_CA_CERT
    service:
      port: 8888
    livenessProbe:
      httpGet:
        path: /healthz
        port: 8888
    readinessProbe:
      httpGet:
        path: /healthz
        port: 8888
# Default webhook-provider-read-timeout (5s) is too tight for the dns-webhook
# sidecar's occasional cold-start call to the control plane, which crashloops
# the main container on a slow-but-not-failed response.
extraArgs:
  webhook-provider-read-timeout: 30s
interval: 5m
policy: sync
sources:
  - service
  - ingress
"""


def make_external_dns(control_plane_url: str, webhook_tag: str = DNS_WEBHOOK_VERSION) -> HelmAddon:
    return HelmAddon(
        release_name="external-dns",
        namespace="external-dns",
        chart="external-dns/external-dns",
        version="1.21.1",
        repo_name="external-dns",
        repo_url="https://kubernetes-sigs.github.io/external-dns",
        values_yaml=_EXTERNAL_DNS_VALUES_TEMPLATE.format(
            image=DNS_WEBHOOK_IMAGE,
            tag=webhook_tag,
            control_plane_url=control_plane_url,
            secret=_CREDENTIALS_SECRET,
        ),
        detect=("deployment", "external-dns"),
    )


def helm_repos_for(addons: list[HelmAddon]) -> dict[str, str]:
    return {a.repo_name: a.repo_url for a in addons if a.repo_name and a.repo_url}


KUBEBLOCKS_VERSION = "v1.0.2"
KUBEBLOCKS_NAMESPACE = "kb-system"
KUBEBLOCKS_CRDS_URL = (
    f"https://github.com/apecloud/kubeblocks/releases/download/{KUBEBLOCKS_VERSION}/"
    "kubeblocks_crds.yaml"
)

SNAPSHOT_CONTROLLER_VERSION = "v8.2.0"
_SNAPSHOT_CRD_BASE = (
    f"https://raw.githubusercontent.com/kubernetes-csi/external-snapshotter/"
    f"{SNAPSHOT_CONTROLLER_VERSION}/client/config/crd"
)
SNAPSHOT_CRD_URLS = [
    f"{_SNAPSHOT_CRD_BASE}/snapshot.storage.k8s.io_volumesnapshotclasses.yaml",
    f"{_SNAPSHOT_CRD_BASE}/snapshot.storage.k8s.io_volumesnapshots.yaml",
    f"{_SNAPSHOT_CRD_BASE}/snapshot.storage.k8s.io_volumesnapshotcontents.yaml",
]

# serviceAccount.create is false — terraform-cogrion-aws-eks-managed-node-group's
# kubeblocks-irsa.tf (or its Alicloud RRSA equivalent) already provisions
# kb-system and the kubeblocks/kubeblocks-dataprotection-* ServiceAccounts
# with the cloud-specific workload-identity annotations.
_KUBEBLOCKS_VALUES_TEMPLATE = """\
nodeSelector:
  nodegroup: system
dataprotection:
  enabled: true
serviceAccount:
  create: false
backupRepo:
  create: false
  default: true
  accessMethod: Tool
  storageProvider: "{storage_provider}"
  pvReclaimPolicy: "Retain"
  volumeCapacity: ""
  config:
    bucket: {bucket}
    endpoint: "{endpoint}"
    region: {region}
"""


def make_kubeblocks(backup_bucket: str, backup_region: str, provider: str) -> HelmAddon:
    if provider == "aws":
        storage_provider = "s3"
        endpoint = ""
    elif provider == "alicloud":
        storage_provider = "oss"
        endpoint = f"oss-{backup_region}.aliyuncs.com"
    else:
        raise ValueError(f"make_kubeblocks: unsupported provider {provider!r}")

    return HelmAddon(
        release_name="kubeblocks",
        namespace=KUBEBLOCKS_NAMESPACE,
        chart="kubeblocks/kubeblocks",
        version=KUBEBLOCKS_VERSION,
        repo_name="kubeblocks",
        repo_url="https://apecloud.github.io/helm-charts",
        values_yaml=_KUBEBLOCKS_VALUES_TEMPLATE.format(
            storage_provider=storage_provider,
            bucket=backup_bucket,
            endpoint=endpoint,
            region=backup_region,
        ),
        detect=("deployment", "kubeblocks"),
    )
