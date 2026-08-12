"""In-memory AWS console simulator for cloud training labs.

Server-authoritative, gradeable mirror of the frontend awsStore.js. State is a
per-session dict cached in Redis/LocMem (same as the 13 sibling engines) and is
persisted to LabSession.simulation_snapshot for worker restarts. The JSON shapes
mirror awsStore.js seedState() exactly so the frontend store can later become a
thin cache over this engine — do NOT invent a new shape here.

Models the core gradeable resources: EC2 instances (pending->running lifecycle
advanced on wall-clock in get_state, start/stop/reboot/terminate, tags, security
groups, instance_type/ami/subnet), S3 buckets + objects, IAM users/roles/policies,
and VPC/subnets/security-group rules. Dependency validation raises real AWS error
strings (DependencyViolation, BucketNotEmpty) mirroring the console.
"""

from __future__ import annotations

import copy
import json
import random
import re
import time
from typing import Any

from django.core.cache import cache

from .aws_v2_facades import apply_v2_action, ensure_v2, seed_v2

SESSION_TTL = 7200
ACCOUNT_ID = "123456789012"

# Wall-clock seconds a freshly launched / started instance stays "pending" before
# get_state() advances it to "running" (mirrors the frontend status-check delay).
PENDING_SECONDS = 5
STOPPING_SECONDS = 3
IMPORT_SECONDS = 2


# ── ID / ARN generators (ported from frontend/src/components/aws/lib/ids.js) ──
_HEX = "0123456789abcdef"
_ALNUM = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"


def _hex(n: int) -> str:
    return "".join(random.choice(_HEX) for _ in range(n))


def _alnum(n: int) -> str:
    return "".join(random.choice(_ALNUM) for _ in range(n))


def new_instance_id() -> str:
    return f"i-0{_hex(16)}"


def new_volume_id() -> str:
    return f"vol-0{_hex(16)}"


def new_ami_id() -> str:
    return f"ami-0{_hex(16)}"


def new_sg_id() -> str:
    return f"sg-0{_hex(16)}"


def new_subnet_id() -> str:
    return f"subnet-0{_hex(16)}"


def new_vpc_id() -> str:
    return f"vpc-0{_hex(16)}"


def new_igw_id() -> str:
    return f"igw-0{_hex(16)}"


def new_rtb_id() -> str:
    return f"rtb-0{_hex(16)}"


def new_acl_id() -> str:
    return f"acl-0{_hex(16)}"


def new_nat_id() -> str:
    return f"nat-0{_hex(16)}"


def new_eip_alloc_id() -> str:
    return f"eipalloc-0{_hex(16)}"


def new_key_pair_id() -> str:
    return f"key-0{_hex(16)}"


def new_sg_rule_id() -> str:
    return f"sgr-0{_hex(16)}"


def new_iam_user_id() -> str:
    return f"AIDA{_alnum(16)}"


def new_iam_role_id() -> str:
    return f"AROA{_alnum(16)}"


def new_iam_group_id() -> str:
    return f"AGPA{_alnum(16)}"


def new_access_key_id() -> str:
    return f"AKIA{_alnum(16)}"


# AWS documentation example access-key ID (not a real credential). Split so
# scripts/check-no-secrets-in-git.sh does not treat the seed data as a leak.
_AWS_DOCS_EXAMPLE_ACCESS_KEY = "AKIA" + "IOSFODNN7EXAMPLE"


def arn(service: str, region: str, account: str, resource: str) -> str:
    # S3 and IAM have empty region/account segments in real AWS.
    if service == "s3":
        return f"arn:aws:s3:::{resource}"
    if service == "iam":
        return f"arn:aws:iam::{account}:{resource}"
    return f"arn:aws:{service}:{region}:{account}:{resource}"


def new_private_ip(subnet_base: str) -> str:
    parts = subnet_base.split(".")
    host = 4 + random.randint(0, 4089)
    third = int(parts[2]) + host // 256
    return f"{parts[0]}.{parts[1]}.{third}.{host % 256}"


def new_public_ip() -> str:
    r = lambda: 1 + random.randint(0, 253)  # noqa: E731
    lead = random.choice([3, 18, 34, 44, 52, 54])
    return f"{lead}.{r()}.{r()}.{r()}"


# ── EC2 instance-type catalog (ported from lib/instanceTypes.js) ──────────────
INSTANCE_TYPES: dict[str, dict] = {
    # hourlyUsd = teaching on-demand rates (not live AWS pricing).
    "t2.nano": {"family": "General purpose", "vcpu": 1, "memGiB": 0.5, "arch": "x86_64", "hourlyUsd": 0.0058},
    "t2.micro": {"family": "General purpose", "vcpu": 1, "memGiB": 1, "arch": "x86_64", "freeTier": True, "hourlyUsd": 0.0116},
    "t2.small": {"family": "General purpose", "vcpu": 1, "memGiB": 2, "arch": "x86_64", "hourlyUsd": 0.023},
    "t2.medium": {"family": "General purpose", "vcpu": 2, "memGiB": 4, "arch": "x86_64", "hourlyUsd": 0.0464},
    "t2.large": {"family": "General purpose", "vcpu": 2, "memGiB": 8, "arch": "x86_64", "hourlyUsd": 0.0928},
    "t3.micro": {"family": "General purpose", "vcpu": 2, "memGiB": 1, "arch": "x86_64", "freeTier": True, "hourlyUsd": 0.0104},
    "t3.small": {"family": "General purpose", "vcpu": 2, "memGiB": 2, "arch": "x86_64", "hourlyUsd": 0.0208},
    "t3.medium": {"family": "General purpose", "vcpu": 2, "memGiB": 4, "arch": "x86_64", "hourlyUsd": 0.0416},
    "t3.large": {"family": "General purpose", "vcpu": 2, "memGiB": 8, "arch": "x86_64", "hourlyUsd": 0.0832},
    "t4g.micro": {"family": "General purpose", "vcpu": 2, "memGiB": 1, "arch": "arm64", "freeTier": True, "hourlyUsd": 0.0084},
    "t4g.small": {"family": "General purpose", "vcpu": 2, "memGiB": 2, "arch": "arm64", "hourlyUsd": 0.0168},
    "t4g.medium": {"family": "General purpose", "vcpu": 2, "memGiB": 4, "arch": "arm64", "hourlyUsd": 0.0336},
    "m5.large": {"family": "General purpose", "vcpu": 2, "memGiB": 8, "arch": "x86_64", "hourlyUsd": 0.096},
    "m5.xlarge": {"family": "General purpose", "vcpu": 4, "memGiB": 16, "arch": "x86_64", "hourlyUsd": 0.192},
    "m6g.large": {"family": "General purpose", "vcpu": 2, "memGiB": 8, "arch": "arm64", "hourlyUsd": 0.077},
    "c5.large": {"family": "Compute optimized", "vcpu": 2, "memGiB": 4, "arch": "x86_64", "hourlyUsd": 0.085},
    "c5.xlarge": {"family": "Compute optimized", "vcpu": 4, "memGiB": 8, "arch": "x86_64", "hourlyUsd": 0.17},
    "r5.large": {"family": "Memory optimized", "vcpu": 2, "memGiB": 16, "arch": "x86_64", "hourlyUsd": 0.126},
    "r5.xlarge": {"family": "Memory optimized", "vcpu": 4, "memGiB": 32, "arch": "x86_64", "hourlyUsd": 0.252},
    # GPU — highest-value FinOps teaching surface (forgotten training jobs).
    "g4dn.xlarge": {
        "family": "GPU", "vcpu": 4, "memGiB": 16, "arch": "x86_64",
        "hourlyUsd": 0.526, "gpu": True,
    },
    "p3.2xlarge": {
        "family": "GPU", "vcpu": 8, "memGiB": 61, "arch": "x86_64",
        "hourlyUsd": 3.06, "gpu": True,
    },
}


def get_instance_type(t: str) -> dict:
    return INSTANCE_TYPES.get(t) or INSTANCE_TYPES["t2.micro"]


# Teaching rates for non-EC2 line items (USD).
_EBS_GB_HOURLY = 0.10 / (30 * 24)  # ~$0.10/GB-month
_EIP_IDLE_HOURLY = 0.005
_NAT_HOURLY = 0.045
_SNAP_GB_HOURLY = 0.05 / (30 * 24)


def estimate_cost_and_usage(state: dict, *, hours: float = 24.0) -> dict:
    """Derived FinOps metric: learners can move cost by stopping/deleting resources."""
    hours = max(0.0, float(hours))
    lines: list[dict] = []
    total = 0.0

    for inst in state.get("instances") or []:
        if inst.get("state") not in ("running", "pending"):
            continue
        meta = get_instance_type(str(inst.get("type") or "t2.micro"))
        rate = float(meta.get("hourlyUsd") or 0.0116)
        amt = round(rate * hours, 4)
        total += amt
        lines.append({
            "service": "AmazonEC2",
            "resource": inst.get("id"),
            "name": inst.get("name"),
            "type": inst.get("type"),
            "tags": dict(inst.get("tags") or {}),
            "gpu": bool(meta.get("gpu")),
            "amount": amt,
            "unit": "USD",
        })

    for vol in state.get("volumes") or []:
        size = float(vol.get("size") or 0)
        amt = round(size * _EBS_GB_HOURLY * hours, 4)
        if amt <= 0:
            continue
        total += amt
        lines.append({
            "service": "AmazonEBS",
            "resource": vol.get("id"),
            "state": vol.get("state"),
            "attachedTo": vol.get("attachedTo"),
            "amount": amt,
            "unit": "USD",
        })

    for snap in state.get("snapshots") or []:
        size = float(snap.get("size") or snap.get("volumeSize") or 8)
        amt = round(size * _SNAP_GB_HOURLY * hours, 4)
        total += amt
        lines.append({
            "service": "AmazonEBS",
            "resource": snap.get("id"),
            "orphaned": bool(snap.get("orphaned")),
            "amount": amt,
            "unit": "USD",
        })

    for eip in state.get("elasticIps") or []:
        if eip.get("associationId") or eip.get("instanceId"):
            continue
        amt = round(_EIP_IDLE_HOURLY * hours, 4)
        total += amt
        lines.append({
            "service": "AmazonVPC",
            "resource": eip.get("allocationId"),
            "kind": "IdleElasticIP",
            "amount": amt,
            "unit": "USD",
        })

    for nat in state.get("natGateways") or []:
        amt = round(_NAT_HOURLY * hours, 4)
        total += amt
        lines.append({
            "service": "AmazonVPC",
            "resource": nat.get("id"),
            "kind": "NATGateway",
            "amount": amt,
            "unit": "USD",
        })

    by_service: dict[str, float] = {}
    for row in lines:
        by_service[row["service"]] = round(by_service.get(row["service"], 0.0) + row["amount"], 4)

    gpu_lines = [r for r in lines if r.get("gpu")]
    return {
        "hours": hours,
        "total": round(total, 4),
        "by_service": by_service,
        "lines": lines,
        "gpu_spend": round(sum(r["amount"] for r in gpu_lines), 4),
        "anomaly_hints": (
            ["GPU instances still running — likely forgotten training job"]
            if gpu_lines else []
        ),
    }


# Classic/Xen families still boot without ENA. Nitro (t3/t4g/c5/r5/…) requires it.
_XEN_CLASSIC_FAMILIES = frozenset({
    "t1", "t2", "m1", "m2", "m3", "c1", "c3", "r3", "i2", "hs1",
})


def instance_requires_ena(itype: str) -> bool:
    family = (itype or "").split(".", 1)[0]
    return family not in _XEN_CLASSIC_FAMILIES


def ami_has_ena(ami: dict | None) -> bool:
    """Whether an AMI advertises the Elastic Network Adapter driver.

    Explicit ``ena`` / ``ena_support`` / ``ena_driver`` False on the AMI or its
    Packer manifest fails closed. An explicit drivers list that omits ``ena``
    likewise fails. Catalog / modern images default to True.
    """
    if not ami:
        return True
    if "ena" in ami:
        return bool(ami["ena"])
    if "ena_support" in ami:
        return bool(ami["ena_support"])
    manifest = ami.get("manifest") if isinstance(ami.get("manifest"), dict) else {}
    if "ena" in manifest:
        return bool(manifest["ena"])
    if "ena_driver" in manifest:
        return bool(manifest["ena_driver"])
    if "ena_support" in manifest:
        return bool(manifest["ena_support"])
    drivers = manifest.get("drivers")
    if isinstance(drivers, list) and drivers:
        return "ena" in {str(d).lower() for d in drivers}
    return True


AMI_CATALOG: dict[str, dict] = {
    "ami-0c02fb55956c7d316": {"os": "amazon-linux-2023", "platform": "Linux/UNIX", "arch": "x86_64", "user": "ec2-user", "ena": True},
    "ami-0557a15b87f6559cf": {"os": "ubuntu-22.04", "platform": "Ubuntu", "arch": "x86_64", "user": "ubuntu", "ena": True},
    "ami-0e001c9271cf7f3b9": {"os": "ubuntu-24.04", "platform": "Ubuntu", "arch": "x86_64", "user": "ubuntu", "ena": True},
    "ami-026ebd4cfe2c043b2": {"os": "rhel-9", "platform": "Red Hat", "arch": "x86_64", "user": "ec2-user", "ena": True},
    "ami-0arm64al2023abc01": {"os": "amazon-linux-2023", "platform": "Linux/UNIX", "arch": "arm64", "user": "ec2-user", "ena": True},
    # Teaching AMI: boots on classic (t2) but Nitro launch refuses (audit X3 ENA).
    "ami-0noenalegacy00001": {
        "os": "amazon-linux-1", "platform": "Linux/UNIX", "arch": "x86_64",
        "user": "ec2-user", "ena": False, "desc": "Legacy image without ENA driver",
    },
}


def get_ami(ami_id: str) -> dict:
    """Catalog lookup with a public-AMI fallback (legacy call sites).

    Prefer :func:`resolve_ami` when a session state is available — custom AMIs
    from ``import_image`` live only on the session and must not silently map to
    Amazon Linux.
    """
    return AMI_CATALOG.get(ami_id) or AMI_CATALOG["ami-0c02fb55956c7d316"]


def resolve_ami(state: dict, ami_id: str) -> dict | None:
    """Resolve an AMI id against session-registered images, then the catalog.

    Returns ``None`` when the id is unknown — callers must surface
    ``InvalidAMIID.NotFound`` rather than inventing a default image.
    """
    for ami in state.get("amis") or []:
        if ami.get("id") == ami_id:
            return ami
    return AMI_CATALOG.get(ami_id)


def _import_manifest_error(manifest: object) -> str | None:
    """Fail-closed gate for ImportImage. Returns an AWS-shaped error or None."""
    from apps.vmware_sim.packer_factory import MANIFEST_SCHEMA_VERSION

    if not isinstance(manifest, dict) or not manifest:
        return "ClientError: Disk validation failed. No image manifest provided."
    if manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        return (
            "ClientError: Disk validation failed. Unsupported or missing "
            f"manifest schema_version (expected {MANIFEST_SCHEMA_VERSION})."
        )
    digest = str(manifest.get("digest") or "").strip()
    if not digest.startswith("sha256:"):
        return "ClientError: Disk validation failed. Manifest digest missing or invalid."
    if not manifest.get("os") or not manifest.get("arch"):
        return "ClientError: Disk validation failed. Manifest missing os/arch."
    return None


def _complete_import_task(state: dict, task: dict) -> dict:
    """Register the AMI carried by a completed ImportImage task."""
    manifest = task.get("manifest") or {}
    quarantined = bool(manifest.get("cve_open"))
    ami = {
        "id": task.get("ami_id") or new_ami_id(),
        "region": state.get("region", "us-east-1"),
        "name": task.get("name") or f"imported-{manifest.get('sku') or 'image'}",
        "os": manifest.get("os") or "ubuntu-22.04",
        "platform": "Linux/UNIX",
        "arch": manifest.get("arch") or "x86_64",
        "user": manifest.get("default_user") or "ubuntu",
        "desc": f"Imported from Image Factory digest {manifest.get('digest')}",
        "owner": ACCOUNT_ID,
        "created": _now_iso(),
        "visibility": "private",
        "manifest": manifest,
        "digest": manifest.get("digest"),
        "quarantined": quarantined,
        "source": "import-image",
    }
    task["ami_id"] = ami["id"]
    state.setdefault("amis", []).append(ami)
    return ami


# ── Session cache helpers (identical contract to terraform_engine.py) ─────────
def _session_key(session_id: str) -> str:
    return f"aws_session:{session_id}"


def _load(session_id: str) -> dict | None:
    data = cache.get(_session_key(str(session_id)))
    if data is None:
        return None
    return json.loads(data) if isinstance(data, str) else data


def _save(session_id: str, entry: dict) -> None:
    cache.set(_session_key(str(session_id)), json.dumps(entry, default=str), SESSION_TTL)


def clear_session(session_id: str) -> None:
    """Remove AWS lab state when the parent lab session terminates."""
    cache.delete(_session_key(str(session_id)))


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _now() -> float:
    return time.time()


# ── Base world (mirrors awsStore.js seedState JSON shapes) ────────────────────
def _base_state() -> dict:
    return {
        "account": {
            "id": ACCOUNT_ID,
            "alias": "fixitlab-enterprise",
            "email": "admin@example.com",
            "rootEmail": "root@example.com",
        },
        "region": "us-east-1",
        "vpcs": [
            {"id": "vpc-0a1b2c3d4e5f67890", "region": "us-east-1", "name": "", "cidr": "172.31.0.0/16", "state": "available", "isDefault": True, "dnsHostnames": True, "dnsSupport": True, "tenancy": "default"},
        ],
        "subnets": [
            {"id": "subnet-0a1b2c3d4e5f10001", "region": "us-east-1", "vpcId": "vpc-0a1b2c3d4e5f67890", "cidr": "172.31.0.0/20", "az": "us-east-1a", "availableIps": 4091, "mapPublicIp": True, "isDefault": True},
            {"id": "subnet-0a1b2c3d4e5f10002", "region": "us-east-1", "vpcId": "vpc-0a1b2c3d4e5f67890", "cidr": "172.31.16.0/20", "az": "us-east-1b", "availableIps": 4091, "mapPublicIp": True, "isDefault": True},
            {"id": "subnet-0a1b2c3d4e5f10003", "region": "us-east-1", "vpcId": "vpc-0a1b2c3d4e5f67890", "cidr": "172.31.32.0/20", "az": "us-east-1c", "availableIps": 4091, "mapPublicIp": False, "isDefault": False},
        ],
        "internetGateways": [
            {"id": "igw-0a1b2c3d4e5f67891", "region": "us-east-1", "vpcId": "vpc-0a1b2c3d4e5f67890", "state": "attached", "name": ""},
        ],
        "routeTables": [
            {"id": "rtb-0a1b2c3d4e5f67892", "region": "us-east-1", "vpcId": "vpc-0a1b2c3d4e5f67890", "main": True, "associations": ["subnet-0a1b2c3d4e5f10001", "subnet-0a1b2c3d4e5f10002", "subnet-0a1b2c3d4e5f10003"], "routes": [{"dest": "172.31.0.0/16", "target": "local"}, {"dest": "0.0.0.0/0", "target": "igw-0a1b2c3d4e5f67891"}]},
        ],
        "networkAcls": [
            {
                "id": "acl-0a1b2c3d4e5f67893", "region": "us-east-1", "vpcId": "vpc-0a1b2c3d4e5f67890", "default": True,
                "associations": ["subnet-0a1b2c3d4e5f10001", "subnet-0a1b2c3d4e5f10002", "subnet-0a1b2c3d4e5f10003"],
                "inbound": [
                    {"rule": 100, "protocol": "-1", "action": "allow", "cidr": "0.0.0.0/0", "from": 0, "to": 65535},
                    {"rule": 32767, "protocol": "-1", "action": "deny", "cidr": "0.0.0.0/0", "from": 0, "to": 65535},
                ],
                "outbound": [
                    {"rule": 100, "protocol": "-1", "action": "allow", "cidr": "0.0.0.0/0", "from": 0, "to": 65535},
                    {"rule": 32767, "protocol": "-1", "action": "deny", "cidr": "0.0.0.0/0", "from": 0, "to": 65535},
                ],
            },
        ],
        "natGateways": [],
        "vpcEndpoints": [],
        "account_id": ACCOUNT_ID,
        "securityGroups": [
            {"id": "sg-0a1b2c3web00001", "region": "us-east-1", "name": "web-sg", "description": "Allow web traffic", "vpcId": "vpc-0a1b2c3d4e5f67890", "inbound": [
                {"id": "sgr-1", "type": "SSH", "protocol": "TCP", "from": 22, "to": 22, "source": "0.0.0.0/0", "description": "SSH"},
                {"id": "sgr-2", "type": "HTTP", "protocol": "TCP", "from": 80, "to": 80, "source": "0.0.0.0/0", "description": "HTTP"},
                {"id": "sgr-3", "type": "HTTPS", "protocol": "TCP", "from": 443, "to": 443, "source": "0.0.0.0/0", "description": "HTTPS"},
            ], "outbound": [{"id": "sgr-o1", "type": "All traffic", "protocol": "All", "from": 0, "to": 65535, "source": "0.0.0.0/0", "description": ""}]},
            {"id": "sg-0a1b2c3db000002", "region": "us-east-1", "name": "db-sg", "description": "Database access", "vpcId": "vpc-0a1b2c3d4e5f67890", "inbound": [
                {"id": "sgr-4", "type": "MySQL/Aurora", "protocol": "TCP", "from": 3306, "to": 3306, "source": "sg-0a1b2c3web00001", "description": "MySQL from web"},
                {"id": "sgr-5", "type": "PostgreSQL", "protocol": "TCP", "from": 5432, "to": 5432, "source": "sg-0a1b2c3web00001", "description": "PG from web"},
            ], "outbound": [{"id": "sgr-o2", "type": "All traffic", "protocol": "All", "from": 0, "to": 65535, "source": "0.0.0.0/0", "description": ""}]},
            {"id": "sg-0a1b2c3default03", "region": "us-east-1", "name": "default", "description": "default VPC security group", "vpcId": "vpc-0a1b2c3d4e5f67890", "inbound": [{"id": "sgr-d", "type": "All traffic", "protocol": "All", "from": 0, "to": 65535, "source": "self", "description": ""}], "outbound": [{"id": "sgr-od", "type": "All traffic", "protocol": "All", "from": 0, "to": 65535, "source": "0.0.0.0/0", "description": ""}]},
        ],
        "keyPairs": [
            {"id": "key-0aa11demo000001", "region": "us-east-1", "name": "demo-key-pair", "type": "rsa", "fingerprint": "a1:b2:c3:d4:e5:f6:01:02:03:04:05:06:07:08:09:0a", "created": "2024-01-15T09:00:00Z"},
            {"id": "key-0bb22prod000002", "region": "us-east-1", "name": "production-key", "type": "ed25519", "fingerprint": "SHA256:Zm9vYmFyMTIzNDU2Nzg5MGFiY2RlZmdoaWprbA", "created": "2024-02-20T11:30:00Z"},
        ],
        "volumes": [
            {"id": "vol-0abc123def456789a", "region": "us-east-1", "size": 8, "type": "gp3", "state": "in-use", "az": "us-east-1a", "encrypted": True, "attachedTo": "i-0abc123def4567890", "device": "/dev/xvda", "created": "2024-01-15T09:00:00Z"},
            {"id": "vol-0def456abc789012b", "region": "us-east-1", "size": 20, "type": "gp3", "state": "in-use", "az": "us-east-1b", "encrypted": False, "attachedTo": "i-0def456abc7890123", "device": "/dev/xvda", "created": "2024-01-16T09:00:00Z"},
            {"id": "vol-0ghi789jkl012345c", "region": "us-east-1", "size": 20, "type": "gp3", "state": "in-use", "az": "us-east-1c", "encrypted": False, "attachedTo": "i-0ghi789jkl0123456", "device": "/dev/xvda", "created": "2024-01-17T09:00:00Z"},
            {"id": "vol-0jkl012mno345678d", "region": "us-east-1", "size": 50, "type": "gp3", "state": "available", "az": "us-east-1a", "encrypted": False, "attachedTo": None, "device": None, "created": "2024-02-01T09:00:00Z"},
        ],
        "amis": [
            {"id": "ami-0custom00web0001", "region": "us-east-1", "name": "my-web-server-ami", "os": "amazon-linux-2023", "platform": "Linux/UNIX", "arch": "x86_64", "user": "ec2-user", "desc": "Created from web-server-01", "owner": ACCOUNT_ID, "created": "2024-03-01T09:00:00Z", "visibility": "private"},
        ],
        "importImageTasks": [],
        "snapshots": [],
        "elasticIps": [
            {"allocationId": "eipalloc-0abc123def4567a", "region": "us-east-1", "publicIp": "54.210.123.45", "associationId": "eipassoc-0abc123def4567b", "instanceId": "i-0abc123def4567890", "domain": "vpc"},
        ],
        "instances": [
            {
                "id": "i-0abc123def4567890", "region": "us-east-1", "name": "web-server-01", "state": "running",
                "amiId": "ami-0c02fb55956c7d316", "os": "amazon-linux-2023", "type": "t2.micro", "az": "us-east-1a",
                "subnetId": "subnet-0a1b2c3d4e5f10001", "vpcId": "vpc-0a1b2c3d4e5f67890",
                "publicIp": "54.210.123.45", "privateIp": "172.31.14.52", "keyName": "demo-key-pair",
                "securityGroups": ["sg-0a1b2c3web00001"], "iamRole": "EC2InstanceRole", "monitoring": "disabled",
                "rootDevice": "/dev/xvda", "rootVolume": "vol-0abc123def456789a", "launchTime": "2024-01-15T09:00:12Z",
                "statusChecks": "2/2", "tenancy": "default", "architecture": "x86_64",
                "tags": {"Name": "web-server-01", "Environment": "demo", "Project": "fixitlab"},
            },
            {
                "id": "i-0def456abc7890123", "region": "us-east-1", "name": "db-server-01", "state": "running",
                "amiId": "ami-0557a15b87f6559cf", "os": "ubuntu-22.04", "type": "t3.small", "az": "us-east-1b",
                "subnetId": "subnet-0a1b2c3d4e5f10002", "vpcId": "vpc-0a1b2c3d4e5f67890",
                "publicIp": "", "privateIp": "172.31.28.33", "keyName": "demo-key-pair",
                "securityGroups": ["sg-0a1b2c3db000002"], "iamRole": "", "monitoring": "disabled",
                "rootDevice": "/dev/xvda", "rootVolume": "vol-0def456abc789012b", "launchTime": "2024-01-16T10:22:00Z",
                "statusChecks": "2/2", "tenancy": "default", "architecture": "x86_64",
                "tags": {"Name": "db-server-01", "Environment": "demo"},
            },
            {
                "id": "i-0ghi789jkl0123456", "region": "us-east-1", "name": "app-server-01", "state": "stopped",
                "amiId": "ami-026ebd4cfe2c043b2", "os": "rhel-9", "type": "t3.medium", "az": "us-east-1c",
                "subnetId": "subnet-0a1b2c3d4e5f10003", "vpcId": "vpc-0a1b2c3d4e5f67890",
                "publicIp": "", "privateIp": "172.31.42.11", "keyName": "demo-key-pair",
                "securityGroups": ["sg-0a1b2c3web00001"], "iamRole": "", "monitoring": "disabled",
                "rootDevice": "/dev/xvda", "rootVolume": "vol-0ghi789jkl012345c", "launchTime": "2024-02-10T08:00:00Z",
                "statusChecks": "0/2", "tenancy": "default", "architecture": "x86_64",
                "tags": {"Name": "app-server-01"},
            },
        ],
        "s3Buckets": [
            {
                "name": "my-web-assets-demo-123456", "region": "us-east-1", "created": "2024-01-10T09:00:00Z",
                "versioning": True, "publicAccess": "Objects can be public", "encryption": "SSE-S3", "website": True,
                "objects": [
                    {"key": "index.html", "size": 4302, "modified": "2024-03-01T10:00:00Z", "storageClass": "STANDARD"},
                    {"key": "style.css", "size": 8112, "modified": "2024-03-01T10:00:00Z", "storageClass": "STANDARD"},
                    {"key": "images/hero.jpg", "size": 251000, "modified": "2024-03-01T10:00:00Z", "storageClass": "STANDARD"},
                ],
            },
            {
                "name": "my-backups-demo-123456", "region": "us-east-1", "created": "2024-01-12T09:00:00Z",
                "versioning": True, "publicAccess": "Bucket and objects not public", "encryption": "SSE-S3", "website": False,
                "objects": [
                    {"key": "backups/2024-03-01/db.tar.gz", "size": 10485760, "modified": "2024-03-01T03:00:00Z", "storageClass": "STANDARD_IA"},
                ],
            },
            {
                "name": "my-logs-demo-123456", "region": "us-east-1", "created": "2024-01-12T09:00:00Z",
                "versioning": False, "publicAccess": "Bucket and objects not public", "encryption": "None", "website": False,
                "objects": [],
            },
        ],
        "iamUsers": [
            {"id": new_iam_user_id(), "name": "admin-user", "created": "2024-01-05T09:00:00Z", "consoleAccess": True, "groups": ["Administrators"], "policies": ["AdministratorAccess"], "accessKeys": []},
            {"id": new_iam_user_id(), "name": "developer-user", "created": "2024-01-06T09:00:00Z", "consoleAccess": True, "groups": ["Developers"], "policies": ["PowerUserAccess"], "accessKeys": [{"id": _AWS_DOCS_EXAMPLE_ACCESS_KEY, "created": "2024-01-06T09:05:00Z", "status": "Active", "lastUsed": "2024-03-10"}]},
            {"id": new_iam_user_id(), "name": "readonly-user", "created": "2024-01-07T09:00:00Z", "consoleAccess": True, "groups": ["ReadOnly"], "policies": ["ReadOnlyAccess"], "accessKeys": []},
        ],
        # Seeded "git history" blobs for X5a leaked-key labs (not real git).
        # Key id is split like _AWS_DOCS_EXAMPLE_ACCESS_KEY so secret scanners stay green.
        "git_history": [
            {
                "sha": "deadbeef01",
                "path": "config/.env.old",
                "blob": (
                    "AWS_ACCESS_KEY_ID=" + "AKIA" + "IOSFODNN7EXAMPLE" + "\n"
                    "AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY\n"
                ),
            },
            {"sha": "cafebabe02", "path": "README.md", "blob": "# safe docs\nNo credentials here.\n"},
        ],
        "invalidated_keys": [],
        "iamGroups": [
            {"id": new_iam_group_id(), "name": "Administrators", "created": "2024-01-05T09:00:00Z", "users": ["admin-user"], "policies": ["AdministratorAccess"]},
            {"id": new_iam_group_id(), "name": "Developers", "created": "2024-01-05T09:00:00Z", "users": ["developer-user"], "policies": ["PowerUserAccess"]},
            {"id": new_iam_group_id(), "name": "ReadOnly", "created": "2024-01-05T09:00:00Z", "users": ["readonly-user"], "policies": ["ReadOnlyAccess"]},
        ],
        "iamRoles": [
            {"id": new_iam_role_id(), "name": "EC2InstanceRole", "created": "2024-01-05T09:00:00Z", "trustedEntity": "ec2.amazonaws.com", "policies": ["AmazonS3ReadOnlyAccess", "CloudWatchAgentServerPolicy"]},
            {"id": new_iam_role_id(), "name": "LambdaExecutionRole", "created": "2024-01-05T09:00:00Z", "trustedEntity": "lambda.amazonaws.com", "policies": ["AWSLambdaBasicExecutionRole"]},
            # Cross-account teaching role (audit X5a AssumeRole + ExternalId).
            {
                "id": new_iam_role_id(), "name": "CrossAccountReadRole", "created": "2024-01-08T09:00:00Z",
                "trustedEntity": "arn:aws:iam::999999999999:root",
                "external_id": "fixitlab-ext-42",
                "policies": ["ReadOnlyAccess"],
                "trust_policy": {
                    "Version": "2012-10-17",
                    "Statement": [{
                        "Effect": "Allow",
                        "Principal": {"AWS": "arn:aws:iam::999999999999:root"},
                        "Action": "sts:AssumeRole",
                        "Condition": {"StringEquals": {"sts:ExternalId": "fixitlab-ext-42"}},
                    }],
                },
            },
            # IRSA / OIDC teaching role (X5a static keys → workload identity).
            {
                "id": new_iam_role_id(), "name": "AppIRSARole", "created": "2024-01-09T09:00:00Z",
                "trustedEntity": "oidc",
                "oidc_provider": "oidc.eks.us-east-1.amazonaws.com/id/EXAMPLED429",
                "oidc_sub": "system:serviceaccount:default:app",
                "policies": ["AmazonS3ReadOnlyAccess"],
                "trust_policy": {
                    "Version": "2012-10-17",
                    "Statement": [{
                        "Effect": "Allow",
                        "Principal": {
                            "Federated": (
                                f"arn:aws:iam::{ACCOUNT_ID}:oidc-provider/"
                                "oidc.eks.us-east-1.amazonaws.com/id/EXAMPLED429"
                            ),
                        },
                        "Action": "sts:AssumeRoleWithWebIdentity",
                        "Condition": {
                            "StringEquals": {
                                "oidc.eks.us-east-1.amazonaws.com/id/EXAMPLED429:sub": (
                                    "system:serviceaccount:default:app"
                                ),
                            },
                        },
                    }],
                },
            },
        ],
        "org_policies": {
            # Fail-open by default; scenarios opt in via set_org_policy.
            "require_ebs_encryption": False,
            "required_tags": [],  # e.g. ["Environment", "Owner"]
        },
        "oidcProviders": [],
        "budgets": [],
        "logGroups": [
            {
                "name": "/aws/lambda/checkout",
                "region": "us-east-1",
                "retentionDays": 30,
                "logLevel": "DEBUG",  # teaching: debug left on in prod
                "ingestedGbPerDay": 12.0,
            },
        ],
        "reservedInstances": [],
        "savingsPlans": [],
        "iamPolicies": [
            {"name": "MyS3BucketPolicy", "type": "Customer managed", "attached": 1, "created": "2024-01-20T09:00:00Z", "description": "Allows access to a specific S3 bucket", "document": {"Version": "2012-10-17", "Statement": [{"Effect": "Allow", "Action": ["s3:GetObject", "s3:PutObject"], "Resource": "arn:aws:s3:::my-web-assets-demo-123456/*"}]}},
            {"name": "MyEC2Policy", "type": "Customer managed", "attached": 0, "created": "2024-01-20T09:00:00Z", "description": "EC2 read + start/stop for tagged resources", "document": {"Version": "2012-10-17", "Statement": [{"Effect": "Allow", "Action": ["ec2:Describe*", "ec2:StartInstances", "ec2:StopInstances"], "Resource": "*"}]}},
            # Excessive-scope teaching policy (X5a least privilege).
            {"name": "OverpoweredDeployPolicy", "type": "Customer managed", "attached": 1, "created": "2024-02-01T09:00:00Z", "description": "Deploy bot with Action=*", "document": {"Version": "2012-10-17", "Statement": [{"Effect": "Allow", "Action": "*", "Resource": "*"}]}},
        ],
        "cwAlarms": [
            {"name": "HighCPUUtilization", "region": "us-east-1", "metric": "CPUUtilization", "namespace": "AWS/EC2", "state": "OK", "threshold": "> 80% for 2/3 datapoints"},
        ],
        "goal": {"title": "AWS console lab", "objective": "Use the AWS console to fix the misconfigured resource."},
        "broken": {},
        "events": [],
        **seed_v2(),
    }


# ── Academy pack (academy-aws-*) per-slug objectives ─────────────────────────
# The 420 academy-aws-* scenarios are generated from a fixed taxonomy:
#   academy-aws-<NNN>-<category>-<service>[-<n>]
# so the mapping keys off that structure rather than substring matching. The
# free-form `in slug` heuristics below in _apply_preset are greedy — 'sg' alone
# matched every *-security-groups-* pack and nothing else, so 400 of 420 packs
# seeded an empty `broken` and the remaining 20 all got the same SSH objective.
#
# A service is listed here ONLY when the console world can model both the break
# and the fix: the marker must be clearable through an action that
# apply_action/apply_v2_action actually implements and the frontend actually
# exposes. Services whose console pages are read-only inventory (guardduty,
# cost-explorer, organizations, trusted-advisor, …) are deliberately absent —
# see _ACADEMY_UNMAPPED_OK. Grading those in the console would mean an
# objective the learner has no control to satisfy, so they stay on the terminal
# sentinel path instead.
_ACADEMY_SLUG_RE = re.compile(r"^academy-aws-\d+-([a-z]+)-([a-z0-9-]+?)(?:-\d+)?$")


def _academy_parts(slug: str) -> tuple[str, str] | None:
    """Split an academy-aws slug into (category, service). None if not academy."""
    m = _ACADEMY_SLUG_RE.match((slug or "").lower())
    if not m:
        return None
    return m.group(1), m.group(2)


def _academy_objective(state: dict, category: str, service: str) -> bool:
    """Seed goal + broken markers for one academy service/category pair.

    Returns True when a marker was seeded. The break is applied to the base
    world here so the console genuinely starts unhealthy — a marker without a
    corresponding break would grade as already-solved on session start.
    """
    # ── EC2 compute ──────────────────────────────────────────────────────────
    if service == "ec2":
        if category in ("learn", "build", "integration"):
            state["goal"] = {"title": "Launch the missing app instance", "objective": "Launch a t3.micro instance named app-web-01 and wait for it to reach the running state."}
            state["broken"] = {"require_launch": {"type": "t3.micro", "name": "app-web-01"}}
            return True
        if category in ("troubleshoot", "operate", "production"):
            # app-server-01 ships stopped in the base inventory — recovery lab.
            state["goal"] = {"title": "Recover the stopped app server", "objective": "Start the stopped app-server-01 instance and confirm it reaches the running state."}
            state["broken"] = {"require_running": "app-server-01"}
            return True
        if category in ("automation", "observability", "backup", "security"):
            state["goal"] = {"title": "Tag the database instance", "objective": "Add the tag Environment=production to db-server-01 so automation and cost allocation can find it."}
            state["broken"] = {"require_tag": {"name": "db-server-01", "key": "Environment", "value": "production"}}
            return True
        return False

    # ── Security groups — SSH open to the world ──────────────────────────────
    if service == "security-groups":
        state["goal"] = {"title": "Restrict SSH ingress", "objective": "Remove the 0.0.0.0/0 SSH rule from web-sg so port 22 is not open to the world."}
        state["broken"] = {"restrict_ssh_sg": "web-sg"}
        return True

    # ── S3 — encryption vs public access, split by category ──────────────────
    if service == "s3":
        if category in ("security", "harden", "production"):
            state["goal"] = {"title": "Block public access", "objective": "Turn off public access on my-web-assets-demo-123456 so its objects are no longer world-readable."}
            state["broken"] = {"require_bucket_private": "my-web-assets-demo-123456"}
            return True
        state["goal"] = {"title": "Enable S3 default encryption", "objective": "Enable default encryption (SSE-S3 or SSE-KMS) on my-logs-demo-123456."}
        state["broken"] = {"require_bucket_encrypted": "my-logs-demo-123456"}
        for b in state.get("s3Buckets") or []:
            if b.get("name") == "my-logs-demo-123456":
                b["encryption"] = "None"
                break
        return True

    # ── VPC — the private-subnet workload is down ────────────────────────────
    # NOT require_instance_in_subnet: app-server-01 already sits in
    # subnet-...10003 in the base inventory, so that marker grades as satisfied
    # on session start (a silent auto-pass). It ships *stopped*, so requiring it
    # to be running is a break the console can both present and clear.
    if service in ("vpc", "nat-gateway", "vpc-peering"):
        state["goal"] = {"title": "Restore the private-subnet workload", "objective": "Start the stopped app-server-01 instance in the private subnet subnet-0a1b2c3d4e5f10003 and confirm it reaches the running state."}
        state["broken"] = {"require_running": "app-server-01"}
        for sn in state.get("subnets") or []:
            if sn.get("id") == "subnet-0a1b2c3d4e5f10003":
                sn["mapPublicIp"] = False
                sn["isDefault"] = False
                break
        return True

    # ── CloudWatch — the alarm the runbook depends on is missing ─────────────
    if service == "cloudwatch":
        state["goal"] = {"title": "Create the missing CPU alarm", "objective": "Create a CloudWatch alarm named HighCPUUtilization on the AWS/EC2 CPUUtilization metric."}
        state["broken"] = {"require_cw_alarm": "HighCPUUtilization"}
        # The base world ships this alarm; the lab is to (re)create it.
        state["cwAlarms"] = [
            a for a in (state.get("cwAlarms") or []) if a.get("name") != "HighCPUUtilization"
        ]
        return True

    # ── Lambda — function memory starved / function missing ──────────────────
    if service == "lambda":
        state["goal"] = {"title": "Deploy the order processor", "objective": "Create a Lambda function named order-processor so the queue drains."}
        state["broken"] = {"require_lambda": "order-processor"}
        return True

    # ── RDS/Aurora — replacement database instance ───────────────────────────
    if service in ("rds", "aurora"):
        state["goal"] = {"title": "Provision the reporting database", "objective": "Create an RDS database instance named reporting-db."}
        state["broken"] = {"require_rds": "reporting-db"}
        return True

    # ── DynamoDB — missing table ─────────────────────────────────────────────
    if service == "dynamodb":
        state["goal"] = {"title": "Create the sessions table", "objective": "Create a DynamoDB table named Sessions."}
        state["broken"] = {"require_dynamodb_table": "Sessions"}
        return True

    # ── Auto Scaling — capacity floor too low for the incident ───────────────
    if service == "autoscaling":
        state["goal"] = {"title": "Scale out the web tier", "objective": "Raise the web-asg desired capacity to at least 4 instances to absorb the traffic spike."}
        state["broken"] = {"require_asg_desired": {"name": "web-asg", "min": 4}}
        return True

    # ── Route 53 — the app record was never created ──────────────────────────
    if service == "route53":
        state["goal"] = {"title": "Restore the app DNS record", "objective": "Create an A record named app in a Route 53 hosted zone so the service resolves again."}
        state["broken"] = {"require_route53_record": {"name": "app", "type": "A"}}
        return True

    # ── IAM — least-privilege role for the workload ──────────────────────────
    if service == "iam":
        state["goal"] = {"title": "Attach the instance role", "objective": "Attach the EC2InstanceRole instance profile to db-server-01 so it can reach S3 without static keys."}
        state["broken"] = {"require_instance_role": {"name": "db-server-01", "role": "EC2InstanceRole"}}
        return True

    return False


# Academy services whose console pages are inventory/read-only in this sim, so
# no console objective can be authored for them. They intentionally stay on the
# terminal sentinel path; listed explicitly so the coverage test can assert the
# set is deliberate rather than an accidental gap.
_ACADEMY_UNMAPPED_OK = frozenset({
    "acm", "api-gateway", "athena", "aws-backup", "cloudformation", "cloudfront",
    "cloudtrail", "cognito", "config", "cost-explorer", "ebs", "ecr",
    "ecs-fargate", "efs", "eks", "elasticache", "elb-alb", "eventbridge", "glue",
    "guardduty", "kinesis", "kms", "nlb", "organizations", "redshift",
    "secrets-manager", "ses", "sns", "sqs", "ssm-parameter-store",
    "ssm-session-manager", "step-functions", "sts-assume-role",
    "transit-gateway", "waf",
})


def _apply_academy_preset(state: dict, slug: str) -> bool:
    """Seed a console objective for an academy-aws-* slug. False when unmapped."""
    parts = _academy_parts(slug)
    if not parts:
        return False
    category, service = parts
    return _academy_objective(state, category, service)


def _apply_preset(state: dict, slug: str) -> None:
    """Seed a scenario-specific broken world + objective from the slug heuristics."""
    slug = (slug or "").lower()
    # Academy packs are structurally named — resolve them before the greedy
    # substring rules below, which would otherwise map every *-security-groups-*
    # pack (and nothing else) onto the SSH objective.
    if slug.startswith("academy-aws-"):
        _apply_academy_preset(state, slug)
        return
    if "launch" in slug or "ec2-launch" in slug:
        state["goal"] = {"title": "Launch EC2 instance", "objective": "Launch a t3.micro instance named app-web-01 and wait for it to reach the running state."}
        state["broken"] = {"require_launch": {"type": "t3.micro", "name": "app-web-01"}}
    elif "stop" in slug and "instance" in slug:
        state["goal"] = {"title": "Stop instance", "objective": "Stop the running web-server-01 instance to save cost."}
        state["broken"] = {"require_stopped": "web-server-01"}
    elif "restart" in slug or "reboot" in slug:
        state["goal"] = {"title": "Recover stopped app server", "objective": "Start the stopped app-server-01 instance and confirm it is running."}
        state["broken"] = {"require_running": "app-server-01"}
        # app-server-01 already stopped in the base inventory.
    elif "sg" in slug or "security-group" in slug or "ingress" in slug:
        state["goal"] = {"title": "Restrict SSH ingress", "objective": "Remove the 0.0.0.0/0 SSH rule from web-sg so port 22 is not open to the world."}
        state["broken"] = {"restrict_ssh_sg": "web-sg"}
    elif "encrypt" in slug or "s3-encrypt" in slug:
        state["goal"] = {"title": "Enable S3 encryption", "objective": "Enable default encryption (SSE-S3 or SSE-KMS) on my-logs-demo-123456."}
        state["broken"] = {"require_bucket_encrypted": "my-logs-demo-123456"}
        for b in state.get("s3Buckets") or []:
            if b.get("name") == "my-logs-demo-123456":
                b["encryption"] = "None"
                break
    elif "bucket" in slug and ("public" in slug or "block" in slug):
        state["goal"] = {"title": "Block public access", "objective": "Turn off public access on my-web-assets-demo-123456."}
        state["broken"] = {"require_bucket_private": "my-web-assets-demo-123456"}
    elif "private-subnet" in slug or "private_subnet" in slug:
        state["goal"] = {"title": "Move workload to private subnet", "objective": "Launch an instance in the private subnet (subnet-0a1b2c3d4e5f10003)."}
        state["broken"] = {"require_instance_in_subnet": "subnet-0a1b2c3d4e5f10003"}
        for sn in state.get("subnets") or []:
            if sn.get("id") == "subnet-0a1b2c3d4e5f10003":
                sn["mapPublicIp"] = False
                sn["isDefault"] = False
                break
    elif "tag" in slug:
        state["goal"] = {"title": "Tag the instance", "objective": "Add the tag Environment=production to db-server-01."}
        state["broken"] = {"require_tag": {"name": "db-server-01", "key": "Environment", "value": "production"}}
    elif (
        "golden-image" in slug or "golden_image" in slug
        or "import-image" in slug or "import_image" in slug
        or "packer-ami" in slug or "ami-from-packer" in slug
        or "packer-to-ec2" in slug
    ):
        state["goal"] = {
            "title": "Publish golden image to EC2",
            "objective": (
                "Build and publish a Packer image, import it as an AMI, launch an "
                "instance from that AMI, and confirm the guest matches the artifact."
            ),
        }
        state["broken"] = {
            "require_image_chain": {
                "packages": ["cloud-init", "openssh-server"],
                "require_guest": True,
            },
        }


# ── Lifecycle advancement on wall-clock (called from get_state) ───────────────
def _advance_lifecycle(state: dict) -> bool:
    """Advance pending->running, stopping->stopped, etc. based on elapsed wall time.

    Mirrors the frontend setTimeout transitions but server-authoritative: a
    transition target + timestamp is stored on the instance and applied when the
    caller next reads state. Returns True if anything changed (caller re-saves).
    """
    changed = False
    now = _now()
    for inst in state.get("instances", []):
        pending = inst.get("_transition")
        if not pending:
            continue
        target_state = pending.get("state")
        at = pending.get("at", 0)
        if now >= at:
            inst["state"] = target_state
            if target_state == "running":
                inst["statusChecks"] = "2/2"
            elif target_state in ("stopped", "terminated"):
                inst["statusChecks"] = "-"
                if target_state == "terminated":
                    inst["publicIp"] = ""
            inst.pop("_transition", None)
            changed = True

    for task in state.get("importImageTasks") or []:
        pending = task.get("_transition")
        if not pending:
            continue
        at = pending.get("at", 0)
        if now < at:
            # Surface progress so DescribeImportImageTasks is not a boolean.
            elapsed = max(0.0, now - (pending.get("started_at") or (at - IMPORT_SECONDS)))
            task["progress"] = min(99, int(100 * elapsed / max(IMPORT_SECONDS, 0.001)))
            task["statusMessage"] = "Converting"
            changed = True
            continue
        target = pending.get("status") or "completed"
        task["status"] = target
        task["progress"] = 100 if target == "completed" else 0
        task["statusMessage"] = "Completed" if target == "completed" else "Deleted"
        task.pop("_transition", None)
        if target == "completed" and not task.get("ami_id"):
            ami = _complete_import_task(state, task)
            _event(state, f"ImportImage {task.get('id')} registered AMI {ami['id']}", "success")
        changed = True
    return changed


def _ensure(session_id: str, slug: str = "") -> dict:
    entry = _load(session_id)
    if entry is None:
        state = _base_state()
        _apply_preset(state, slug)
        entry = {"session_id": str(session_id), "scenario_slug": slug, "state": state}
        _save(session_id, entry)
    return entry


# Alias used by the provisioner dispatch (mirrors terraform_engine `_ensure`).
_ensure_session = _ensure


def get_state(session_id: str, scenario_slug: str = "") -> dict:
    entry = _ensure(session_id, scenario_slug)
    keys_before = set(entry["state"].keys())
    ensure_v2(entry["state"])
    if set(entry["state"].keys()) != keys_before:
        _save(session_id, entry)
    if _advance_lifecycle(entry["state"]):
        _save(session_id, entry)
    slug = entry.get("scenario_slug") or scenario_slug
    state = copy.deepcopy(entry["state"])
    # Scenario-owned Lab Server: mirror primary EC2 into server_identity so the
    # terminal Hosted as: AWS EC2 Instance matches the console instance.
    try:
        from apps.labs.provisioner.simulation.server_identity import sync_aws_instance
        primary = next(
            (i for i in (state.get("instances") or []) if (i.get("state") or "") != "terminated"),
            None,
        )
        if primary:
            sync_aws_instance(str(session_id), primary, instance_types=INSTANCE_TYPES)
    except Exception:
        pass
    return {
        "session_id": str(session_id),
        "scenario_slug": slug,
        "state": state,
        "goal": state.get("goal", {}),
        "events": state.get("events", []),
    }


def drop_session(session_id: str) -> None:
    cache.delete(_session_key(str(session_id)))


# ── Helpers ───────────────────────────────────────────────────────────────────
def _find_instance(state: dict, ident: str) -> dict | None:
    for inst in state.get("instances", []):
        if inst.get("id") == ident or inst.get("name") == ident or (inst.get("tags") or {}).get("Name") == ident:
            return inst
    return None


def _event(state: dict, message: str, severity: str = "info") -> None:
    state.setdefault("events", []).insert(0, {"time": _now_iso(), "message": message, "severity": severity})


def apply_action(session_id: str, action: str, payload: dict | None = None) -> dict:
    payload = payload or {}
    entry = _load(session_id)
    if not entry:
        return {"ok": False, "error": "AWS session not found"}
    state = entry["state"]
    # Fold any due lifecycle transitions in before mutating.
    _advance_lifecycle(state)
    region = state.get("region", "us-east-1")

    # ── EC2 launch ────────────────────────────────────────────────────────────
    if action == "launch_instance":
        name = (payload.get("name") or "").strip()
        itype = payload.get("instance_type") or payload.get("type") or "t2.micro"
        if itype not in INSTANCE_TYPES:
            return {"ok": False, "error": f"The instance type '{itype}' does not exist"}
        ami_id = payload.get("ami_id") or payload.get("amiId") or "ami-0c02fb55956c7d316"
        ami = resolve_ami(state, ami_id)
        if ami is None:
            return {
                "ok": False,
                "error": f"InvalidAMIID.NotFound: The image id '[{ami_id}]' does not exist",
            }
        if ami.get("quarantined"):
            return {
                "ok": False,
                "error": (
                    "UnauthorizedOperation: The AMI is quarantined pending "
                    "vulnerability remediation"
                ),
            }
        if ami.get("deprecated") or ami.get("deprecationTime"):
            return {
                "ok": False,
                "error": (
                    f"InvalidAMIID.Unavailable: The image id '[{ami_id}]' is deprecated "
                    "and cannot be used to launch new instances."
                ),
            }
        # Cross-account private AMI requires an explicit launch permission (X3).
        caller = str(state.get("account_id") or ACCOUNT_ID)
        owner = str(ami.get("owner") or "")
        visibility = str(ami.get("visibility") or "public").lower()
        if owner and owner != caller and visibility != "public":
            perms = ami.get("launchPermissions") or {}
            user_ids = [str(u) for u in (perms.get("UserIds") or perms.get("userIds") or [])]
            if caller not in user_ids:
                return {
                    "ok": False,
                    "error": (
                        "UnauthorizedOperation: You are not authorized to perform this "
                        "operation. The AMI has no launch permission for this account."
                    ),
                }
        ami_arch = str(ami.get("arch") or "x86_64")
        type_arch = str(get_instance_type(itype).get("arch") or "x86_64")
        if ami_arch != type_arch:
            return {
                "ok": False,
                "error": (
                    f"InvalidParameterCombination: The architecture '{ami_arch}' of the "
                    f"specified AMI is incompatible with the architecture '{type_arch}' of "
                    f"the specified instance type."
                ),
            }
        if instance_requires_ena(itype) and not ami_has_ena(ami):
            return {
                "ok": False,
                "error": (
                    f"InvalidParameterCombination: The specified instance type '{itype}' "
                    "requires the Elastic Network Adapter (ENA) driver, which is not "
                    "present in the selected AMI."
                ),
            }
        count = int(payload.get("count") or 1)
        subnet_id = payload.get("subnet_id") or payload.get("subnetId") or ""
        subnets = state.get("subnets", [])
        subnet = next((s for s in subnets if s.get("id") == subnet_id), None) or next((s for s in subnets if s.get("region") == region), None)
        if subnet_id and subnet is None:
            return {"ok": False, "error": f"The subnet ID '{subnet_id}' does not exist"}
        sg_ids = payload.get("security_groups") or payload.get("securityGroups") or ["sg-0a1b2c3default03"]
        key_name = payload.get("key_name") or payload.get("keyName") or ""
        tags = payload.get("tags") or {}
        if not isinstance(tags, dict):
            tags = {}
        required = list((state.get("org_policies") or {}).get("required_tags") or [])
        if required:
            missing = [k for k in required if not str((tags.get(k) if tags else "") or "").strip()]
            # Name alone never satisfies required_tags.
            if name and "Name" in required and "Name" not in tags:
                tags = {**tags, "Name": name}
                missing = [k for k in required if not str(tags.get(k) or "").strip()]
            if missing:
                return {
                    "ok": False,
                    "error": (
                        "TagPolicyViolation: Your organization requires tags "
                        f"{required}. Missing: {missing}."
                    ),
                }
        az = (subnet or {}).get("az") or f"{region}a"
        created = []
        for _ in range(max(1, count)):
            iid = new_instance_id()
            base = (subnet or {}).get("cidr", "172.31.16.0/20").split("/")[0]
            priv = new_private_ip(base)
            pub = new_public_ip() if (subnet or {}).get("mapPublicIp") else ""
            rootvol = new_volume_id()
            inst_tags = {**({"Name": name} if name else {}), **tags}
            inst = {
                "id": iid, "region": region, "name": name, "state": "pending",
                "amiId": ami_id, "os": ami.get("os") or "amazon-linux-2023", "type": itype, "az": az,
                "subnetId": (subnet or {}).get("id", ""), "vpcId": (subnet or {}).get("vpcId", ""),
                "publicIp": pub, "privateIp": priv, "keyName": key_name,
                "securityGroups": list(sg_ids), "iamRole": "", "monitoring": "enabled" if payload.get("monitoring") else "disabled",
                "rootDevice": "/dev/xvda", "rootVolume": rootvol, "launchTime": _now_iso(),
                "statusChecks": "initializing", "tenancy": "default", "architecture": get_instance_type(itype)["arch"],
                "tags": inst_tags,
                # Carry the image manifest so guest seed / grading can derive
                # packages, kernel, and users from the AMI the learner imported.
                "manifest": ami.get("manifest"),
                "amiDigest": ami.get("digest") or (ami.get("manifest") or {}).get("digest"),
                "_transition": {"state": "running", "at": _now() + PENDING_SECONDS},
            }
            state.setdefault("instances", []).append(inst)
            state.setdefault("volumes", []).append({
                "id": rootvol, "region": region, "size": int(payload.get("volume_size") or 8),
                "type": payload.get("volume_type") or "gp3", "state": "in-use", "az": az,
                "encrypted": bool(payload.get("volume_encrypted")), "attachedTo": iid, "device": "/dev/xvda", "created": _now_iso(),
            })
            created.append(iid)
        _event(state, f"Launched {len(created)} instance(s): {', '.join(created)}", "success")
        _save(session_id, entry)
        try:
            from apps.labs.provisioner.simulation.server_identity import sync_aws_instance
            for iid in created:
                inst = _find_instance(state, iid)
                if inst:
                    sync_aws_instance(str(session_id), inst, instance_types=INSTANCE_TYPES)
        except Exception:
            pass
        return {"ok": True, "message": "RunInstances succeeded", "instance_ids": created}

    # ── EC2 lifecycle: start / stop / reboot / terminate ───────────────────────
    if action in ("start_instance", "stop_instance", "reboot_instance", "terminate_instance", "instance_action"):
        op = payload.get("op") or {
            "start_instance": "start", "stop_instance": "stop",
            "reboot_instance": "reboot", "terminate_instance": "terminate",
        }.get(action, payload.get("action") or "start")
        ids = payload.get("instance_ids") or payload.get("ids")
        if not ids:
            single = payload.get("instance_id") or payload.get("id")
            ids = [single] if single else []
        transitions = {
            "start": ("pending", "running", PENDING_SECONDS),
            "stop": ("stopping", "stopped", STOPPING_SECONDS),
            "reboot": ("rebooting", "running", PENDING_SECONDS),
            "terminate": ("shutting-down", "terminated", STOPPING_SECONDS),
        }
        if op not in transitions:
            return {"ok": False, "error": f"Unknown instance op: {op}"}
        interim, final, delay = transitions[op]
        touched = []
        for ident in ids:
            inst = _find_instance(state, ident)
            if not inst:
                return {"ok": False, "error": f"The instance ID '{ident}' does not exist"}
            if op == "start" and inst.get("state") not in ("stopped", "running"):
                return {"ok": False, "error": f"IncorrectInstanceState: instance {inst.get('id')} is not in a state from which it can be started"}
            inst["state"] = interim
            inst["statusChecks"] = "initializing" if op in ("start", "reboot") else "-"
            inst["_transition"] = {"state": final, "at": _now() + delay}
            touched.append(inst.get("id"))
        _event(state, f"{op} requested for {', '.join(touched)}", "info")
        _save(session_id, entry)
        try:
            from apps.labs.provisioner.simulation.server_identity import sync_aws_instance
            for ident in touched:
                inst = _find_instance(state, ident)
                if inst:
                    sync_aws_instance(str(session_id), inst, instance_types=INSTANCE_TYPES)
        except Exception:
            pass
        return {"ok": True, "message": f"{op} initiated", "instance_ids": touched}

    # ── EC2 tags ───────────────────────────────────────────────────────────────
    if action == "set_tags":
        ident = payload.get("instance_id") or payload.get("id") or payload.get("name")
        inst = _find_instance(state, ident)
        if not inst:
            return {"ok": False, "error": f"The instance ID '{ident}' does not exist"}
        tags = payload.get("tags") or {}
        if not isinstance(tags, dict):
            return {"ok": False, "error": "Invalid tags payload"}
        inst.setdefault("tags", {}).update({str(k): str(v) for k, v in tags.items()})
        if "Name" in tags:
            inst["name"] = str(tags["Name"])
        _event(state, f"Tags updated on {inst.get('id')}", "info")
        _save(session_id, entry)
        return {"ok": True, "message": "CreateTags succeeded"}

    # ── EBS volume attach (also used by the bridge_attach_volume API action) ──
    if action == "attach_volume":
        vol_id = payload.get("volume_id") or payload.get("id")
        inst_id = payload.get("instance_id") or payload.get("instance") or ""
        device = payload.get("device") or "/dev/sdf"
        inst = _find_instance(state, inst_id) if inst_id else None
        vol = next((v for v in state.get("volumes", []) if v.get("id") == vol_id), None)
        if vol is None:
            vol = {
                "id": vol_id or new_volume_id(), "region": region,
                "size": int(payload.get("size_gb") or 20), "type": payload.get("volume_type") or "gp3",
                "state": "available", "az": (inst or {}).get("az") or f"{region}a",
                "encrypted": bool(payload.get("encrypted")), "attachedTo": None, "device": None,
                "created": _now_iso(),
            }
            state.setdefault("volumes", []).append(vol)
        vol["state"] = "in-use"
        vol["attachedTo"] = inst_id or vol.get("attachedTo")
        vol["device"] = device
        _event(state, f"Volume {vol['id']} attached to {inst_id or 'instance'} at {device}", "success")
        _save(session_id, entry)
        try:
            from apps.labs.provisioner.simulation import aws_bridge
            aws_bridge.record_volume_attach(
                str(session_id),
                vol["id"],
                size_gb=int(vol.get("size") or 20),
                device=device,
                instance_id=inst_id or None,
            )
        except Exception:
            pass
        return {"ok": True, "message": "AttachVolume succeeded", "volume_id": vol["id"], "device": device}

    # ── EBS volume detach (also used by the bridge_detach_volume API action) ──
    if action == "detach_volume":
        vol_id = payload.get("volume_id") or payload.get("id")
        vol = next((v for v in state.get("volumes", []) if v.get("id") == vol_id), None)
        if not vol:
            return {"ok": False, "error": f"The volume '{vol_id}' does not exist."}
        inst = _find_instance(state, vol.get("attachedTo")) if vol.get("attachedTo") else None
        if inst and inst.get("rootVolume") == vol_id and inst.get("state") != "terminated":
            return {"ok": False, "error": f"'{vol_id}' is the root device and cannot be detached while the instance is running"}
        device = vol.get("device")
        vol["state"] = "available"
        vol["attachedTo"] = None
        vol["device"] = None
        _event(state, f"Volume {vol_id} detached", "info")
        _save(session_id, entry)
        try:
            from apps.labs.provisioner.simulation import aws_bridge
            if device:
                aws_bridge.record_volume_detach(str(session_id), device, instance_id=inst.get("id") if inst else None)
        except Exception:
            pass
        return {"ok": True, "message": "DetachVolume succeeded", "volume_id": vol_id, "device": device}

    # ── Security group ingress/egress rules ───────────────────────────────────
    if action in ("add_sg_rule", "remove_sg_rule"):
        sg_ident = payload.get("group_id") or payload.get("group_name") or payload.get("sg")
        sg = next((g for g in state.get("securityGroups", []) if g.get("id") == sg_ident or g.get("name") == sg_ident), None)
        if not sg:
            return {"ok": False, "error": f"The security group '{sg_ident}' does not exist"}
        direction = payload.get("direction") or "inbound"
        rules = sg.setdefault(direction, [])
        if action == "add_sg_rule":
            rule = {
                "id": new_sg_rule_id(),
                "type": payload.get("type") or "Custom TCP",
                "protocol": payload.get("protocol") or "TCP",
                "from": int(payload.get("from_port") or payload.get("from") or 0),
                "to": int(payload.get("to_port") or payload.get("to") or 0),
                "source": payload.get("source") or payload.get("cidr") or "0.0.0.0/0",
                "description": payload.get("description") or "",
            }
            rules.append(rule)
            _event(state, f"Ingress rule added to {sg.get('name')}", "info")
            _save(session_id, entry)
            return {"ok": True, "message": "AuthorizeSecurityGroupIngress succeeded", "rule": rule}
        # remove_sg_rule — by rule id, or by (port, source) match.
        rid = payload.get("rule_id")
        port = payload.get("port")
        source = payload.get("source") or payload.get("cidr")
        before = len(rules)
        if rid:
            sg[direction] = [r for r in rules if r.get("id") != rid]
        else:
            def _match(r):
                if port is not None and int(r.get("from", -1)) != int(port):
                    return False
                if source is not None and r.get("source") != source:
                    return False
                return True
            sg[direction] = [r for r in rules if not _match(r)]
        if len(sg[direction]) == before:
            return {"ok": False, "error": "No matching security group rule found"}
        _event(state, f"Ingress rule removed from {sg.get('name')}", "info")
        _save(session_id, entry)
        return {"ok": True, "message": "RevokeSecurityGroupIngress succeeded"}

    if action == "create_security_group":
        name = (payload.get("name") or "new-sg").strip()
        sg = {
            "id": new_sg_id(), "region": region, "name": name,
            "description": payload.get("description") or "", "vpcId": payload.get("vpc_id") or state["vpcs"][0]["id"],
            "inbound": payload.get("inbound") or [],
            "outbound": [{"id": new_sg_rule_id(), "type": "All traffic", "protocol": "All", "from": 0, "to": 65535, "source": "0.0.0.0/0", "description": ""}],
        }
        state.setdefault("securityGroups", []).append(sg)
        _event(state, f"Security group {name} created", "success")
        _save(session_id, entry)
        return {"ok": True, "message": "CreateSecurityGroup succeeded", "group_id": sg["id"]}

    # ── VPC / subnet / SG deletion with DependencyViolation ────────────────────
    if action == "delete_security_group":
        sg_ident = payload.get("group_id") or payload.get("group_name")
        sg = next((g for g in state.get("securityGroups", []) if g.get("id") == sg_ident or g.get("name") == sg_ident), None)
        if not sg:
            return {"ok": False, "error": f"The security group '{sg_ident}' does not exist"}
        attached = [i for i in state.get("instances", []) if sg["id"] in (i.get("securityGroups") or []) and i.get("state") != "terminated"]
        if attached:
            return {"ok": False, "error": f"DependencyViolation: resource {sg['id']} has a dependent object"}
        state["securityGroups"] = [g for g in state["securityGroups"] if g["id"] != sg["id"]]
        _event(state, f"Security group {sg.get('name')} deleted", "info")
        _save(session_id, entry)
        return {"ok": True, "message": "DeleteSecurityGroup succeeded"}

    if action == "delete_subnet":
        sid = payload.get("subnet_id")
        subnet = next((s for s in state.get("subnets", []) if s.get("id") == sid), None)
        if not subnet:
            return {"ok": False, "error": f"The subnet ID '{sid}' does not exist"}
        in_subnet = [i for i in state.get("instances", []) if i.get("subnetId") == sid and i.get("state") != "terminated"]
        if in_subnet:
            return {"ok": False, "error": f"DependencyViolation: The subnet '{sid}' has dependencies and cannot be deleted."}
        state["subnets"] = [s for s in state["subnets"] if s["id"] != sid]
        _event(state, f"Subnet {sid} deleted", "info")
        _save(session_id, entry)
        return {"ok": True, "message": "DeleteSubnet succeeded"}

    if action == "delete_vpc":
        vid = payload.get("vpc_id")
        vpc = next((v for v in state.get("vpcs", []) if v.get("id") == vid), None)
        if not vpc:
            return {"ok": False, "error": f"The vpc ID '{vid}' does not exist"}
        deps = (
            [s for s in state.get("subnets", []) if s.get("vpcId") == vid]
            or [i for i in state.get("instances", []) if i.get("vpcId") == vid and i.get("state") != "terminated"]
        )
        if deps:
            return {"ok": False, "error": f"DependencyViolation: The vpc '{vid}' has dependencies and cannot be deleted."}
        state["vpcs"] = [v for v in state["vpcs"] if v["id"] != vid]
        _event(state, f"VPC {vid} deleted", "info")
        _save(session_id, entry)
        return {"ok": True, "message": "DeleteVpc succeeded"}

    if action == "create_subnet":
        vpc_id = payload.get("vpc_id") or state["vpcs"][0]["id"]
        subnet = {
            "id": payload.get("subnet_id") or new_subnet_id(), "region": region, "vpcId": vpc_id,
            "cidr": payload.get("cidr") or "172.31.48.0/20", "az": payload.get("az") or f"{region}a",
            "availableIps": 4091, "mapPublicIp": bool(payload.get("map_public_ip")), "isDefault": False,
        }
        state.setdefault("subnets", []).append(subnet)
        _event(state, f"Subnet {subnet['id']} created", "success")
        _save(session_id, entry)
        return {"ok": True, "message": "CreateSubnet succeeded", "subnet_id": subnet["id"]}

    if action == "create_vpc":
        vpc = {
            "id": payload.get("vpc_id") or new_vpc_id(),
            "region": region,
            "name": payload.get("name") or "",
            "cidr": payload.get("cidr") or "10.0.0.0/16",
            "state": "available",
            "isDefault": False,
            "dnsHostnames": False,
            "dnsSupport": True,
            "tenancy": payload.get("tenancy") or "default",
        }
        state.setdefault("vpcs", []).append(vpc)
        _event(state, f"VPC {vpc['id']} created", "success")
        _save(session_id, entry)
        return {"ok": True, "message": "CreateVpc succeeded", "vpc_id": vpc["id"]}

    if action == "create_volume":
        vol = {
            "id": payload.get("volume_id") or new_volume_id(),
            "region": region,
            "size": int(payload.get("size_gb") or payload.get("size") or 8),
            "type": payload.get("volume_type") or payload.get("type") or "gp3",
            "state": "available",
            "az": payload.get("az") or f"{region}a",
            "encrypted": bool(payload.get("encrypted")),
            "attachedTo": None,
            "device": None,
            "created": _now_iso(),
        }
        state.setdefault("volumes", []).append(vol)
        _event(state, f"Volume {vol['id']} created", "success")
        _save(session_id, entry)
        return {"ok": True, "message": "CreateVolume succeeded", "volume_id": vol["id"]}

    if action == "delete_volume":
        vol_id = payload.get("volume_id") or payload.get("id")
        vol = next((v for v in state.get("volumes", []) if v.get("id") == vol_id), None)
        if not vol:
            return {"ok": False, "error": f"The volume '{vol_id}' does not exist."}
        if vol.get("state") == "in-use":
            return {"ok": False, "error": f"Volume '{vol_id}' is currently attached and cannot be deleted."}
        state["volumes"] = [v for v in state["volumes"] if v.get("id") != vol_id]
        _event(state, f"Volume {vol_id} deleted", "info")
        _save(session_id, entry)
        return {"ok": True, "message": "DeleteVolume succeeded"}

    if action == "create_snapshot":
        vol_id = payload.get("volume_id") or ""
        vol = next((v for v in state.get("volumes", []) if v.get("id") == vol_id), None)
        encrypted = bool((vol or {}).get("encrypted"))
        if "encrypted" in payload:
            encrypted = bool(payload.get("encrypted"))
        kms_key = (payload.get("kms_key_id") or payload.get("kms_key") or "").strip()
        if kms_key:
            encrypted = True
        org = state.get("org_policies") or {}
        if org.get("require_ebs_encryption") and not encrypted:
            return {
                "ok": False,
                "error": (
                    "SnapshotCreationFailed: Your organization requires EBS encryption. "
                    "Create the snapshot Encrypted=true with a KMS key."
                ),
            }
        snap = {
            "id": payload.get("snapshot_id") or f"snap-{_hex(17)}",
            "region": region,
            "volumeId": vol_id,
            "size": (vol or {}).get("size") or int(payload.get("size") or 8),
            "state": "completed",
            "progress": "100%",
            "description": payload.get("description") or "",
            "started": _now_iso(),
            "encrypted": encrypted,
            "kmsKeyId": kms_key or None,
        }
        state.setdefault("snapshots", []).append(snap)
        _event(state, f"Snapshot {snap['id']} created", "success")
        _save(session_id, entry)
        return {"ok": True, "message": "CreateSnapshot succeeded", "snapshot_id": snap["id"]}

    if action == "delete_snapshot":
        sid = payload.get("snapshot_id") or payload.get("id")
        before = len(state.get("snapshots") or [])
        state["snapshots"] = [s for s in (state.get("snapshots") or []) if s.get("id") != sid]
        if len(state.get("snapshots") or []) == before:
            return {"ok": False, "error": f"The snapshot '{sid}' does not exist."}
        _event(state, f"Snapshot {sid} deleted", "info")
        _save(session_id, entry)
        return {"ok": True, "message": "DeleteSnapshot succeeded"}

    if action == "allocate_eip":
        eip = {
            "allocationId": payload.get("allocation_id") or new_eip_alloc_id(),
            "region": region,
            "publicIp": payload.get("public_ip") or new_public_ip(),
            "associationId": None,
            "instanceId": None,
            "domain": "vpc",
        }
        state.setdefault("elasticIps", []).append(eip)
        _event(state, f"Elastic IP {eip['publicIp']} allocated", "success")
        _save(session_id, entry)
        return {"ok": True, "message": "AllocateAddress succeeded", "allocation_id": eip["allocationId"]}

    if action == "associate_eip":
        alloc = payload.get("allocation_id") or ""
        eip = next((e for e in state.get("elasticIps", []) if e.get("allocationId") == alloc), None)
        if not eip:
            return {"ok": False, "error": f"The allocation ID '{alloc}' does not exist"}
        inst_id = payload.get("instance_id") or ""
        inst = _find_instance(state, inst_id) if inst_id else None
        if not inst:
            return {"ok": False, "error": f"The instance ID '{inst_id}' does not exist"}
        eip["associationId"] = payload.get("association_id") or f"eipassoc-0{_hex(16)}"
        eip["instanceId"] = inst_id
        inst["publicIp"] = eip.get("publicIp") or ""
        _event(state, f"Associated {eip['publicIp']} with {inst_id}", "success")
        _save(session_id, entry)
        return {"ok": True, "message": "AssociateAddress succeeded"}

    if action == "disassociate_eip":
        alloc = payload.get("allocation_id") or ""
        eip = next((e for e in state.get("elasticIps", []) if e.get("allocationId") == alloc), None)
        if not eip:
            return {"ok": False, "error": f"The allocation ID '{alloc}' does not exist"}
        inst_id = eip.get("instanceId")
        if inst_id:
            inst = _find_instance(state, inst_id)
            if inst:
                inst["publicIp"] = ""
        eip["associationId"] = None
        eip["instanceId"] = None
        _event(state, f"Disassociated Elastic IP {eip.get('publicIp')}", "info")
        _save(session_id, entry)
        return {"ok": True, "message": "DisassociateAddress succeeded"}

    if action == "release_eip":
        alloc = payload.get("allocation_id") or ""
        eip = next((e for e in state.get("elasticIps", []) if e.get("allocationId") == alloc), None)
        if not eip:
            return {"ok": False, "error": f"The allocation ID '{alloc}' does not exist"}
        if eip.get("associationId"):
            return {"ok": False, "error": f"The address with allocation id '{alloc}' is currently associated and cannot be released. Disassociate it first."}
        state["elasticIps"] = [e for e in state["elasticIps"] if e.get("allocationId") != alloc]
        _event(state, f"Released Elastic IP {eip.get('publicIp')}", "info")
        _save(session_id, entry)
        return {"ok": True, "message": "ReleaseAddress succeeded"}

    if action == "create_internet_gateway":
        igw = {
            "id": payload.get("igw_id") or new_igw_id(),
            "region": region,
            "vpcId": None,
            "state": "detached",
            "name": payload.get("name") or "",
        }
        state.setdefault("internetGateways", []).append(igw)
        _event(state, f"Internet gateway {igw['id']} created", "success")
        _save(session_id, entry)
        return {"ok": True, "message": "CreateInternetGateway succeeded", "igw_id": igw["id"]}

    if action == "attach_internet_gateway":
        igw_id = payload.get("igw_id") or payload.get("id")
        vpc_id = payload.get("vpc_id") or ""
        igw = next((g for g in state.get("internetGateways", []) if g.get("id") == igw_id), None)
        if not igw:
            return {"ok": False, "error": f"The internetGateway '{igw_id}' does not exist"}
        if any(g.get("vpcId") == vpc_id and g.get("id") != igw_id for g in state.get("internetGateways", [])):
            return {"ok": False, "error": f"resource {vpc_id} already has an internet gateway attached"}
        igw["vpcId"] = vpc_id
        igw["state"] = "attached"
        _event(state, f"Attached {igw_id} to {vpc_id}", "success")
        _save(session_id, entry)
        return {"ok": True, "message": "AttachInternetGateway succeeded"}

    if action == "detach_internet_gateway":
        igw_id = payload.get("igw_id") or payload.get("id")
        igw = next((g for g in state.get("internetGateways", []) if g.get("id") == igw_id), None)
        if not igw:
            return {"ok": False, "error": f"The internetGateway '{igw_id}' does not exist"}
        igw["vpcId"] = None
        igw["state"] = "detached"
        _event(state, f"Detached internet gateway {igw_id}", "info")
        _save(session_id, entry)
        return {"ok": True, "message": "DetachInternetGateway succeeded"}

    if action == "delete_internet_gateway":
        igw_id = payload.get("igw_id") or payload.get("id")
        igw = next((g for g in state.get("internetGateways", []) if g.get("id") == igw_id), None)
        if not igw:
            return {"ok": False, "error": f"The internetGateway '{igw_id}' does not exist"}
        if igw.get("state") == "attached":
            return {"ok": False, "error": f"The internetGateway '{igw_id}' has dependencies and cannot be deleted. Detach it first."}
        state["internetGateways"] = [g for g in state["internetGateways"] if g.get("id") != igw_id]
        _event(state, f"Deleted internet gateway {igw_id}", "info")
        _save(session_id, entry)
        return {"ok": True, "message": "DeleteInternetGateway succeeded"}

    if action == "create_key_pair":
        name = (payload.get("name") or "").strip()
        if not name:
            return {"ok": False, "error": "Key pair name is required"}
        if any(k.get("name") == name for k in state.get("keyPairs", [])):
            return {"ok": False, "error": f"InvalidKeyPair.Duplicate: The keypair '{name}' already exists."}
        kp = {
            "id": payload.get("key_pair_id") or new_key_pair_id(),
            "region": region,
            "name": name,
            "type": payload.get("type") or "rsa",
            "fingerprint": ":".join(f"{random.randint(0, 255):02x}" for _ in range(16)),
            "created": _now_iso(),
        }
        state.setdefault("keyPairs", []).append(kp)
        _event(state, f"Key pair {name} created", "success")
        _save(session_id, entry)
        return {"ok": True, "message": "CreateKeyPair succeeded", "key_pair_id": kp["id"]}

    if action == "delete_key_pair":
        name = payload.get("name") or ""
        before = len(state.get("keyPairs") or [])
        state["keyPairs"] = [k for k in (state.get("keyPairs") or []) if k.get("name") != name]
        if len(state.get("keyPairs") or []) == before:
            return {"ok": False, "error": f"InvalidKeyPair.NotFound: The key pair '{name}' does not exist"}
        _event(state, f"Key pair {name} deleted", "info")
        _save(session_id, entry)
        return {"ok": True, "message": "DeleteKeyPair succeeded"}

    if action == "create_route_table":
        vpc_id = payload.get("vpc_id") or (state.get("vpcs") or [{}])[0].get("id")
        vpc = next((v for v in state.get("vpcs", []) if v.get("id") == vpc_id), None)
        rtb = {
            "id": payload.get("rtb_id") or new_rtb_id(),
            "region": region,
            "vpcId": vpc_id,
            "main": False,
            "associations": [],
            "routes": [{"dest": (vpc or {}).get("cidr") or "10.0.0.0/16", "target": "local"}],
        }
        state.setdefault("routeTables", []).append(rtb)
        _event(state, f"Route table {rtb['id']} created", "success")
        _save(session_id, entry)
        return {"ok": True, "message": "CreateRouteTable succeeded", "rtb_id": rtb["id"]}

    if action == "create_route":
        rtb_id = payload.get("rtb_id") or ""
        rtb = next((r for r in state.get("routeTables", []) if r.get("id") == rtb_id), None)
        if not rtb:
            return {"ok": False, "error": f"The routeTable ID '{rtb_id}' does not exist"}
        dest = payload.get("dest") or "0.0.0.0/0"
        target = payload.get("target") or "igw-local"
        routes = [x for x in (rtb.get("routes") or []) if x.get("dest") != dest]
        routes.append({"dest": dest, "target": target})
        rtb["routes"] = routes
        _event(state, f"Route {dest} → {target} added to {rtb_id}", "success")
        _save(session_id, entry)
        return {"ok": True, "message": "CreateRoute succeeded"}

    if action == "delete_route_table":
        rtb_id = payload.get("rtb_id") or payload.get("id")
        rtb = next((r for r in state.get("routeTables", []) if r.get("id") == rtb_id), None)
        if not rtb:
            return {"ok": False, "error": f"The routeTable ID '{rtb_id}' does not exist"}
        if rtb.get("main"):
            return {"ok": False, "error": f"The main route table '{rtb_id}' cannot be deleted."}
        state["routeTables"] = [r for r in state["routeTables"] if r.get("id") != rtb_id]
        _event(state, f"Route table {rtb_id} deleted", "info")
        _save(session_id, entry)
        return {"ok": True, "message": "DeleteRouteTable succeeded"}

    if action == "associate_route_table":
        rtb_id = payload.get("rtb_id") or ""
        subnet_id = payload.get("subnet_id") or ""
        rtb = next((r for r in state.get("routeTables", []) if r.get("id") == rtb_id), None)
        subnet = next((s for s in state.get("subnets", []) if s.get("id") == subnet_id), None)
        if not rtb:
            return {"ok": False, "error": f"The routeTable ID '{rtb_id}' does not exist"}
        if not subnet:
            return {"ok": False, "error": f"The subnet ID '{subnet_id}' does not exist"}
        for other in state.get("routeTables") or []:
            assocs = list(other.get("associations") or [])
            if subnet_id in assocs and other.get("id") != rtb_id:
                other["associations"] = [a for a in assocs if a != subnet_id]
        assocs = list(rtb.get("associations") or [])
        if subnet_id not in assocs:
            assocs.append(subnet_id)
        rtb["associations"] = assocs
        _event(state, f"Associated {subnet_id} with {rtb_id}", "success")
        _save(session_id, entry)
        return {"ok": True, "message": "AssociateRouteTable succeeded"}

    if action == "disassociate_route_table":
        rtb_id = payload.get("rtb_id") or ""
        subnet_id = payload.get("subnet_id") or ""
        rtb = next((r for r in state.get("routeTables", []) if r.get("id") == rtb_id), None)
        if not rtb:
            return {"ok": False, "error": f"The routeTable ID '{rtb_id}' does not exist"}
        rtb["associations"] = [a for a in (rtb.get("associations") or []) if a != subnet_id]
        _event(state, f"Disassociated {subnet_id} from {rtb_id}", "info")
        _save(session_id, entry)
        return {"ok": True, "message": "DisassociateRouteTable succeeded"}

    if action == "create_network_acl":
        vpc_id = payload.get("vpc_id") or (state.get("vpcs") or [{}])[0].get("id")
        acl = {
            "id": payload.get("acl_id") or new_acl_id(),
            "region": region,
            "vpcId": vpc_id,
            "default": False,
            "associations": [],
            "inbound": [
                {"rule": 32767, "protocol": "-1", "action": "deny", "cidr": "0.0.0.0/0", "from": 0, "to": 65535},
            ],
            "outbound": [
                {"rule": 32767, "protocol": "-1", "action": "deny", "cidr": "0.0.0.0/0", "from": 0, "to": 65535},
            ],
        }
        state.setdefault("networkAcls", []).append(acl)
        _event(state, f"Network ACL {acl['id']} created", "success")
        _save(session_id, entry)
        return {"ok": True, "message": "CreateNetworkAcl succeeded", "acl_id": acl["id"]}

    if action == "delete_network_acl":
        acl_id = payload.get("acl_id") or payload.get("id")
        acl = next((a for a in state.get("networkAcls", []) if a.get("id") == acl_id), None)
        if not acl:
            return {"ok": False, "error": f"The networkAcl ID '{acl_id}' does not exist"}
        if acl.get("default"):
            return {"ok": False, "error": f"The default network ACL '{acl_id}' cannot be deleted."}
        if acl.get("associations"):
            return {"ok": False, "error": f"Network ACL '{acl_id}' has subnet associations"}
        state["networkAcls"] = [a for a in state["networkAcls"] if a.get("id") != acl_id]
        _event(state, f"Network ACL {acl_id} deleted", "info")
        _save(session_id, entry)
        return {"ok": True, "message": "DeleteNetworkAcl succeeded"}

    if action == "create_nacl_entry":
        acl_id = payload.get("acl_id") or ""
        acl = next((a for a in state.get("networkAcls", []) if a.get("id") == acl_id), None)
        if not acl:
            return {"ok": False, "error": f"The networkAcl ID '{acl_id}' does not exist"}
        direction = "outbound" if payload.get("egress") else "inbound"
        rule_row = {
            "rule": int(payload.get("rule") or payload.get("rule_number") or 100),
            "protocol": str(payload.get("protocol") if payload.get("protocol") is not None else "-1"),
            "action": (payload.get("action") or "allow").lower(),
            "cidr": payload.get("cidr") or "0.0.0.0/0",
            "from": int(payload.get("from") or payload.get("from_port") or 0),
            "to": int(payload.get("to") or payload.get("to_port") or 65535),
        }
        rules = [r for r in (acl.get(direction) or []) if r.get("rule") != rule_row["rule"]]
        rules.append(rule_row)
        rules.sort(key=lambda r: r.get("rule", 0))
        acl[direction] = rules
        _event(state, f"NACL entry {rule_row['rule']} on {acl_id}", "success")
        _save(session_id, entry)
        return {"ok": True, "message": "CreateNetworkAclEntry succeeded"}

    if action == "replace_nacl_association":
        acl_id = payload.get("acl_id") or ""
        subnet_id = payload.get("subnet_id") or ""
        acl = next((a for a in state.get("networkAcls", []) if a.get("id") == acl_id), None)
        if not acl:
            return {"ok": False, "error": f"The networkAcl ID '{acl_id}' does not exist"}
        for other in state.get("networkAcls") or []:
            assocs = list(other.get("associations") or [])
            if subnet_id in assocs and other.get("id") != acl_id:
                other["associations"] = [a for a in assocs if a != subnet_id]
        assocs = list(acl.get("associations") or [])
        if subnet_id not in assocs:
            assocs.append(subnet_id)
        acl["associations"] = assocs
        _event(state, f"Associated subnet {subnet_id} with NACL {acl_id}", "success")
        _save(session_id, entry)
        return {"ok": True, "message": "ReplaceNetworkAclAssociation succeeded"}

    if action == "create_nat_gateway":
        subnet_id = payload.get("subnet_id") or (state.get("subnets") or [{}])[0].get("id")
        subnet = next((s for s in state.get("subnets", []) if s.get("id") == subnet_id), None)
        if not subnet:
            return {"ok": False, "error": f"The subnet ID '{subnet_id}' does not exist"}
        alloc = payload.get("allocation_id")
        eip = None
        if alloc:
            eip = next((e for e in state.get("elasticIps", []) if e.get("allocationId") == alloc), None)
        if not eip:
            eip = {
                "allocationId": alloc or new_eip_alloc_id(),
                "region": region,
                "publicIp": payload.get("public_ip") or new_public_ip(),
                "associationId": None,
                "instanceId": None,
                "domain": "vpc",
            }
            state.setdefault("elasticIps", []).append(eip)
        nat = {
            "id": payload.get("nat_id") or new_nat_id(),
            "region": region,
            "subnetId": subnet_id,
            "vpcId": subnet.get("vpcId"),
            "allocationId": eip["allocationId"],
            "publicIp": eip["publicIp"],
            "state": "available",
        }
        state.setdefault("natGateways", []).append(nat)
        _event(state, f"NAT gateway {nat['id']} created", "success")
        _save(session_id, entry)
        return {"ok": True, "message": "CreateNatGateway succeeded", "nat_id": nat["id"]}

    if action == "delete_nat_gateway":
        nat_id = payload.get("nat_id") or payload.get("id")
        before = len(state.get("natGateways") or [])
        state["natGateways"] = [n for n in (state.get("natGateways") or []) if n.get("id") != nat_id]
        if len(state.get("natGateways") or []) == before:
            return {"ok": False, "error": f"The natGateway ID '{nat_id}' does not exist"}
        _event(state, f"NAT gateway {nat_id} deleted", "info")
        _save(session_id, entry)
        return {"ok": True, "message": "DeleteNatGateway succeeded"}

    if action == "create_vpc_endpoint":
        # Gateway endpoint for in-VPC S3/DynamoDB — cuts NAT data-processing (X5b).
        svc = (
            payload.get("service")
            or payload.get("service_name")
            or payload.get("ServiceName")
            or "com.amazonaws.us-east-1.s3"
        ).strip()
        vpc_id = payload.get("vpc_id") or payload.get("vpcId") or (
            (state.get("vpcs") or [{}])[0].get("id") if state.get("vpcs") else ""
        )
        ep_type = payload.get("vpc_endpoint_type") or payload.get("type") or "Gateway"
        ep = {
            "id": payload.get("endpoint_id") or f"vpce-{_hex(17)}",
            "region": region,
            "vpcId": vpc_id,
            "serviceName": svc,
            "vpcEndpointType": ep_type,
            "state": "available",
            "created": _now_iso(),
        }
        state.setdefault("vpcEndpoints", []).append(ep)
        _event(state, f"VPC endpoint {ep['id']} ({svc}) created", "success")
        _save(session_id, entry)
        return {"ok": True, "message": "CreateVpcEndpoint succeeded", "endpoint": ep}

    if action == "delete_vpc_endpoint":
        eid = payload.get("endpoint_id") or payload.get("id")
        before = len(state.get("vpcEndpoints") or [])
        state["vpcEndpoints"] = [
            e for e in (state.get("vpcEndpoints") or []) if e.get("id") != eid
        ]
        if len(state.get("vpcEndpoints") or []) == before:
            return {"ok": False, "error": f"InvalidVpcEndpointId.NotFound: '{eid}'"}
        _save(session_id, entry)
        return {"ok": True, "message": "DeleteVpcEndpoint succeeded"}

    if action in ("estimate_nat_s3_charges", "simulate_s3_via_nat"):
        gb = float(payload.get("gb") or payload.get("gigabytes") or 10)
        # $0.045/GB teaching rate for NAT data processing (not real AWS pricing).
        rate = float(payload.get("rate_per_gb") or 0.045)
        has_s3_vpce = any(
            "s3" in str(e.get("serviceName") or "").lower()
            for e in (state.get("vpcEndpoints") or [])
            if e.get("state") != "deleted"
        )
        has_nat = bool(state.get("natGateways"))
        if not has_nat:
            return {
                "ok": True,
                "message": "No NAT gateway — no NAT data-processing charge",
                "nat_processing_usd": 0.0,
                "via_vpc_endpoint": False,
                "gb": gb,
            }
        if has_s3_vpce:
            return {
                "ok": True,
                "message": "S3 traffic via Gateway VPC endpoint — NAT processing $0",
                "nat_processing_usd": 0.0,
                "via_vpc_endpoint": True,
                "gb": gb,
            }
        charge = round(gb * rate, 4)
        return {
            "ok": True,
            "message": (
                f"S3 traffic hairpinned through NAT: ${charge} "
                f"({gb} GB × ${rate}/GB). Add a Gateway VPC endpoint for S3."
            ),
            "nat_processing_usd": charge,
            "via_vpc_endpoint": False,
            "gb": gb,
        }

    if action == "register_image":
        # Teaching helper: register an AMI (incl. foreign-owned) into the session.
        ami_id = payload.get("ami_id") or payload.get("id") or new_ami_id()
        if any(a.get("id") == ami_id for a in state.get("amis") or []):
            return {"ok": False, "error": f"InvalidAMIID.Duplicate: '{ami_id}' already exists"}
        ami = {
            "id": ami_id,
            "region": payload.get("region") or region,
            "name": payload.get("name") or f"registered-{ami_id[-8:]}",
            "os": payload.get("os") or "amazon-linux-2023",
            "platform": payload.get("platform") or "Linux/UNIX",
            "arch": payload.get("arch") or "x86_64",
            "user": payload.get("user") or "ec2-user",
            "desc": payload.get("description") or "",
            "owner": str(payload.get("owner") or state.get("account_id") or ACCOUNT_ID),
            "created": _now_iso(),
            "visibility": payload.get("visibility") or "private",
            "ena": payload.get("ena", True),
            "launchPermissions": {
                "UserIds": [str(u) for u in (payload.get("user_ids") or [])],
            },
            "deprecated": bool(payload.get("deprecated")),
            "deprecationTime": payload.get("deprecation_time"),
            "snapshotIds": list(payload.get("snapshot_ids") or []),
        }
        if not ami.get("deprecated"):
            ami.pop("deprecationTime", None)
        state.setdefault("amis", []).append(ami)
        _event(state, f"AMI {ami_id} registered (owner={ami['owner']})", "info")
        _save(session_id, entry)
        return {"ok": True, "message": "RegisterImage succeeded", "ami_id": ami_id, "ami": ami}

    if action == "copy_image":
        src_id = payload.get("ami_id") or payload.get("source_ami_id") or payload.get("id") or ""
        src = resolve_ami(state, src_id)
        if src is None:
            return {
                "ok": False,
                "error": f"InvalidAMIID.NotFound: The image id '[{src_id}]' does not exist",
            }
        dest_region = payload.get("destination_region") or payload.get("region") or region
        new_id = payload.get("new_ami_id") or new_ami_id()
        # Copy backing snapshots into the destination region when present.
        new_snap_ids = []
        for sid in list(src.get("snapshotIds") or []):
            old = next((s for s in state.get("snapshots") or [] if s.get("id") == sid), None)
            nsid = f"snap-{_hex(17)}"
            state.setdefault("snapshots", []).append({
                "id": nsid,
                "region": dest_region,
                "volumeId": (old or {}).get("volumeId"),
                "size": (old or {}).get("size") or 8,
                "state": "completed",
                "progress": "100%",
                "description": f"Copied from {sid} for {new_id}",
                "started": _now_iso(),
                "encrypted": bool((old or {}).get("encrypted")),
                "amiId": new_id,
                "sourceSnapshotId": sid,
            })
            new_snap_ids.append(nsid)
        copied = {
            "id": new_id,
            "region": dest_region,
            "name": payload.get("name") or f"{src.get('name') or src_id}-copy",
            "os": src.get("os") or "amazon-linux-2023",
            "platform": src.get("platform") or "Linux/UNIX",
            "arch": src.get("arch") or "x86_64",
            "user": src.get("user") or "ec2-user",
            "desc": payload.get("description") or f"Copied from {src_id}",
            "owner": str(state.get("account_id") or ACCOUNT_ID),
            "created": _now_iso(),
            "visibility": "private",
            "sourceAmiId": src_id,
            "sourceRegion": src.get("region") or region,
            "manifest": src.get("manifest"),
            "digest": src.get("digest"),
            "ena": src.get("ena", True),
            "snapshotIds": new_snap_ids,
            "launchPermissions": {"UserIds": []},
        }
        state.setdefault("amis", []).append(copied)
        _event(state, f"AMI {src_id} copied → {new_id} ({dest_region})", "success")
        _save(session_id, entry)
        return {
            "ok": True,
            "message": "CopyImage succeeded",
            "ami_id": new_id,
            "ami": copied,
        }

    if action in ("modify_image_attribute", "share_image", "unshare_image", "deprecate_image"):
        ami_id = payload.get("ami_id") or payload.get("id") or ""
        ami = next((a for a in (state.get("amis") or []) if a.get("id") == ami_id), None)
        if not ami:
            return {"ok": False, "error": f"InvalidAMIID.NotFound: The image id '[{ami_id}]' does not exist"}
        caller = str(state.get("account_id") or ACCOUNT_ID)
        if str(ami.get("owner") or caller) != caller:
            return {
                "ok": False,
                "error": "UnauthorizedOperation: Only the AMI owner can modify attributes",
            }
        if action == "deprecate_image" or payload.get("deprecate") or payload.get("DeprecationTime"):
            ami["deprecated"] = True
            ami["deprecationTime"] = (
                payload.get("deprecation_time")
                or payload.get("DeprecationTime")
                or _now_iso()
            )
            _event(state, f"AMI {ami_id} deprecated", "info")
            _save(session_id, entry)
            return {"ok": True, "message": "EnableImageDeprecation succeeded", "ami": ami}

        perms = ami.setdefault("launchPermissions", {})
        user_ids = perms.setdefault("UserIds", [])
        targets = payload.get("user_ids") or payload.get("UserIds") or []
        if isinstance(targets, str):
            targets = [targets]
        targets = [str(t) for t in targets]
        op = (payload.get("operation") or payload.get("OperationType") or "add").lower()
        if action == "unshare_image":
            op = "remove"
        elif action == "share_image":
            op = "add"
        if op in ("add", "share"):
            for t in targets:
                if t not in user_ids:
                    user_ids.append(t)
            msg = "Launch permissions added"
        else:
            user_ids[:] = [u for u in user_ids if u not in targets]
            msg = "Launch permissions removed"
        _event(state, f"AMI {ami_id}: {msg} {targets}", "info")
        _save(session_id, entry)
        return {
            "ok": True,
            "message": "ModifyImageAttribute succeeded",
            "launchPermissions": perms,
        }

    if action == "list_image_drift":
        # Instances still on a deprecated AMI (X3 image drift).
        ami_by_id = {a.get("id"): a for a in (state.get("amis") or [])}
        drifted = []
        for inst in state.get("instances") or []:
            if inst.get("state") == "terminated":
                continue
            aid = inst.get("amiId")
            ami = ami_by_id.get(aid) or AMI_CATALOG.get(aid) or {}
            if ami.get("deprecated") or ami.get("deprecationTime"):
                drifted.append({
                    "instance_id": inst.get("id"),
                    "name": inst.get("name"),
                    "ami_id": aid,
                    "ami_name": ami.get("name"),
                    "deprecationTime": ami.get("deprecationTime"),
                })
        return {"ok": True, "drifted_instances": drifted, "count": len(drifted)}

    if action == "create_image":
        inst_id = payload.get("instance_id") or ""
        inst = _find_instance(state, inst_id) if inst_id else None
        if not inst:
            return {"ok": False, "error": f"The instance ID '{inst_id}' does not exist"}
        # Backing snapshot — deregister without DeleteSnapshots leaves orphans (X5b).
        root_vol = next(
            (v for v in state.get("volumes") or [] if v.get("id") == inst.get("rootVolume")),
            None,
        )
        snap = {
            "id": payload.get("snapshot_id") or f"snap-{_hex(17)}",
            "region": region,
            "volumeId": (root_vol or {}).get("id") or inst.get("rootVolume") or "",
            "size": (root_vol or {}).get("size") or 8,
            "state": "completed",
            "progress": "100%",
            "description": f"Created by CreateImage for {inst_id}",
            "started": _now_iso(),
            "encrypted": bool((root_vol or {}).get("encrypted")),
            "amiId": None,  # filled after AMI id known
        }
        ami_id = payload.get("ami_id") or new_ami_id()
        snap["amiId"] = ami_id
        state.setdefault("snapshots", []).append(snap)
        ami = {
            "id": ami_id,
            "region": region,
            "name": payload.get("name") or f"{inst.get('name') or inst_id}-ami",
            "os": inst.get("os") or "amazon-linux-2023",
            "platform": "Linux/UNIX",
            "arch": "x86_64",
            "user": "ec2-user",
            "desc": payload.get("description") or f"Created from {inst_id}",
            "owner": ACCOUNT_ID,
            "created": _now_iso(),
            "visibility": "private",
            "manifest": inst.get("manifest"),
            "digest": inst.get("amiDigest"),
            "snapshotIds": [snap["id"]],
            "blockDeviceMappings": [
                {"deviceName": "/dev/xvda", "snapshotId": snap["id"], "volumeSize": snap["size"]},
            ],
        }
        state.setdefault("amis", []).append(ami)
        _event(state, f"AMI {ami['id']} created from {inst_id}", "success")
        _save(session_id, entry)
        return {
            "ok": True,
            "message": "CreateImage succeeded",
            "ami_id": ami["id"],
            "snapshot_ids": list(ami["snapshotIds"]),
        }

    if action in ("import_image", "import_snapshot"):
        # Packer → AMI bridge (§X3). Fail closed without a real content manifest —
        # a missing/invalid artifact must not invent an AMI (audit: Disk validation
        # failed → no AMI → InvalidAMIID.NotFound on launch).
        manifest = payload.get("manifest")
        if not manifest:
            from apps.vmware_sim import packer_factory as pf
            mres = pf.get_manifest(state)
            if mres.get("ok"):
                manifest = mres["manifest"]
        err = _import_manifest_error(manifest)
        if err:
            return {"ok": False, "error": err}
        expected = str(payload.get("digest") or "").strip()
        if expected and expected != manifest.get("digest"):
            return {
                "ok": False,
                "error": "ClientError: Disk validation failed. Manifest digest mismatch.",
            }
        if action == "import_snapshot":
            snap = {
                "id": payload.get("snapshot_id") or f"snap-0{_hex(16)}",
                "region": region,
                "state": "completed",
                "progress": "100%",
                "volumeSize": int(payload.get("volume_size") or 8),
                "description": payload.get("description") or "Imported snapshot",
                "startTime": _now_iso(),
                "digest": manifest.get("digest"),
                "manifest": manifest,
            }
            state.setdefault("snapshots", []).append(snap)
            _event(state, f"Snapshot {snap['id']} imported", "success")
            _save(session_id, entry)
            return {"ok": True, "message": "ImportSnapshot succeeded", "snapshot_id": snap["id"]}

        task_id = payload.get("task_id") or f"import-ami-{_hex(8)}"
        started = _now()
        task = {
            "id": task_id,
            "status": "active",
            "progress": 1,
            "statusMessage": "Pending",
            "name": payload.get("name") or f"imported-{manifest.get('sku') or 'image'}",
            "manifest": manifest,
            "architecture": manifest.get("arch") or "x86_64",
            "platform": "Linux",
            "_transition": {
                "status": "completed",
                "at": started + IMPORT_SECONDS,
                "started_at": started,
            },
        }
        state.setdefault("importImageTasks", []).append(task)
        _event(state, f"ImportImage task {task_id} started", "info")
        _save(session_id, entry)
        return {
            "ok": True,
            "message": "ImportImage started",
            "import_task_id": task_id,
            "status": task["status"],
        }

    if action == "describe_import_image_tasks":
        tasks = list(state.get("importImageTasks") or [])
        task_id = payload.get("task_id") or payload.get("id")
        if task_id:
            tasks = [t for t in tasks if t.get("id") == task_id]
        return {"ok": True, "import_image_tasks": tasks}

    if action == "deregister_image":
        ami_id = payload.get("ami_id") or payload.get("id")
        ami = next((a for a in (state.get("amis") or []) if a.get("id") == ami_id), None)
        if not ami:
            return {"ok": False, "error": f"The AMI ID '{ami_id}' does not exist"}
        snap_ids = list(ami.get("snapshotIds") or [])
        for bdm in ami.get("blockDeviceMappings") or []:
            sid = bdm.get("snapshotId")
            if sid and sid not in snap_ids:
                snap_ids.append(sid)
        delete_snaps = bool(
            payload.get("delete_snapshots")
            or payload.get("DeleteSnapshots")
            or payload.get("deleteSnapshots")
        )
        orphaned = []
        deleted = []
        snaps = state.setdefault("snapshots", [])
        if delete_snaps and snap_ids:
            keep = []
            for s in snaps:
                if s.get("id") in snap_ids:
                    deleted.append(s.get("id"))
                else:
                    keep.append(s)
            state["snapshots"] = keep
        else:
            for s in snaps:
                if s.get("id") in snap_ids or s.get("amiId") == ami_id:
                    s["orphaned"] = True
                    s["amiId"] = None
                    s.setdefault("orphanedReason", "AMI deregistered without DeleteSnapshots")
                    orphaned.append(s.get("id"))
        state["amis"] = [a for a in (state.get("amis") or []) if a.get("id") != ami_id]
        _event(
            state,
            f"AMI {ami_id} deregistered"
            + (f"; deleted snapshots {deleted}" if deleted else "")
            + (f"; orphaned snapshots {orphaned}" if orphaned else ""),
            "info",
        )
        _save(session_id, entry)
        return {
            "ok": True,
            "message": "DeregisterImage succeeded",
            "orphaned_snapshots": orphaned,
            "deleted_snapshots": deleted,
        }

    if action == "set_termination_protection":
        inst_id = payload.get("instance_id") or payload.get("id")
        inst = _find_instance(state, inst_id)
        if not inst:
            return {"ok": False, "error": f"The instance ID '{inst_id}' does not exist"}
        inst["disableApiTermination"] = bool(payload.get("value"))
        _event(state, f"Termination protection for {inst_id} → {inst['disableApiTermination']}", "info")
        _save(session_id, entry)
        return {"ok": True, "message": "ModifyInstanceAttribute succeeded"}

    if action == "delete_iam_user":
        uname = payload.get("name") or ""
        before = len(state.get("iamUsers") or [])
        state["iamUsers"] = [u for u in (state.get("iamUsers") or []) if u.get("name") != uname]
        if len(state.get("iamUsers") or []) == before:
            return {"ok": False, "error": f"NoSuchEntity: The user with name {uname} cannot be found"}
        _event(state, f"IAM user {uname} deleted", "info")
        _save(session_id, entry)
        return {"ok": True, "message": "DeleteUser succeeded"}

    if action == "create_access_key":
        uname = payload.get("name") or ""
        user = next((u for u in state.get("iamUsers", []) if u.get("name") == uname), None)
        if not user:
            return {"ok": False, "error": f"NoSuchEntity: The user with name {uname} cannot be found"}
        keys = user.setdefault("accessKeys", [])
        # AWS hard limit: two access keys per IAM user (enables dual-key rotation).
        if len(keys) >= 2:
            return {
                "ok": False,
                "error": (
                    "LimitExceeded: Cannot exceed quota for AccessKeysPerUser: 2. "
                    "Deactivate and delete an existing key before creating another."
                ),
            }
        key = {
            "id": payload.get("access_key_id") or new_access_key_id(),
            "created": _now_iso(),
            "status": "Active",
            "lastUsed": "N/A",
        }
        keys.append(key)
        _event(state, f"Access key created for {uname}", "success")
        _save(session_id, entry)
        return {
            "ok": True,
            "message": "CreateAccessKey succeeded",
            "access_key_id": key["id"],
            "access_keys": list(keys),
        }

    if action in ("update_access_key", "deactivate_access_key", "activate_access_key"):
        uname = payload.get("name") or ""
        user = next((u for u in state.get("iamUsers", []) if u.get("name") == uname), None)
        if not user:
            return {"ok": False, "error": f"NoSuchEntity: The user with name {uname} cannot be found"}
        kid = payload.get("access_key_id") or payload.get("id") or ""
        key = next((k for k in user.get("accessKeys") or [] if k.get("id") == kid), None)
        if not key:
            return {"ok": False, "error": f"NoSuchEntity: The Access Key with id {kid} cannot be found"}
        if action == "deactivate_access_key":
            status = "Inactive"
        elif action == "activate_access_key":
            status = "Active"
        else:
            status = payload.get("status") or payload.get("Status") or "Inactive"
            status = "Active" if str(status).lower() in ("active", "true", "1") else "Inactive"
        key["status"] = status
        _event(state, f"Access key {kid} → {status}", "info")
        _save(session_id, entry)
        return {"ok": True, "message": "UpdateAccessKey succeeded", "access_key": key}

    if action == "delete_access_key":
        uname = payload.get("name") or ""
        user = next((u for u in state.get("iamUsers", []) if u.get("name") == uname), None)
        if not user:
            return {"ok": False, "error": f"NoSuchEntity: The user with name {uname} cannot be found"}
        kid = payload.get("access_key_id") or payload.get("id") or ""
        before = len(user.get("accessKeys") or [])
        user["accessKeys"] = [k for k in (user.get("accessKeys") or []) if k.get("id") != kid]
        if len(user.get("accessKeys") or []) == before:
            return {"ok": False, "error": f"NoSuchEntity: The Access Key with id {kid} cannot be found"}
        _event(state, f"Access key {kid} deleted", "info")
        _save(session_id, entry)
        return {"ok": True, "message": "DeleteAccessKey succeeded"}

    if action == "use_access_key":
        # Teaching hook: mark lastUsed so rotation can verify the old key is idle.
        uname = payload.get("name") or ""
        user = next((u for u in state.get("iamUsers", []) if u.get("name") == uname), None)
        if not user:
            return {"ok": False, "error": f"NoSuchEntity: The user with name {uname} cannot be found"}
        kid = payload.get("access_key_id") or payload.get("id") or ""
        key = next((k for k in user.get("accessKeys") or [] if k.get("id") == kid), None)
        if not key:
            return {"ok": False, "error": f"NoSuchEntity: The Access Key with id {kid} cannot be found"}
        if key.get("compromised") or kid in (state.get("invalidated_keys") or []):
            return {
                "ok": False,
                "error": "InvalidClientTokenId: The security token included in the request is invalid "
                         "(key was invalidated after a leak).",
            }
        if key.get("status") != "Active":
            return {"ok": False, "error": "InvalidClientTokenId: The access key is Inactive"}
        key["lastUsed"] = _now_iso()
        _save(session_id, entry)
        return {"ok": True, "message": "Access key used", "access_key": key}

    if action == "detect_leaked_key":
        # Scan in-memory "git history" blobs (X5a) — not real git log.
        import re as _re
        pattern = _re.compile(r"AKIA[0-9A-Z]{16}")
        history = state.get("git_history")
        if history is None:
            state["git_history"] = []
            history = state["git_history"]
        findings = []
        for commit in history:
            blob = commit.get("blob") or ""
            for m in pattern.finditer(blob):
                kid = m.group(0)
                owner = None
                for u in state.get("iamUsers") or []:
                    if any(k.get("id") == kid for k in (u.get("accessKeys") or [])):
                        owner = u.get("name")
                        break
                findings.append({
                    "sha": commit.get("sha"),
                    "path": commit.get("path"),
                    "access_key_id": kid,
                    "user": owner,
                    "source": "git_history",
                })
        _event(state, f"Secret scan: {len(findings)} leaked key(s)", "warning" if findings else "info")
        _save(session_id, entry)
        return {
            "ok": True,
            "leaked": bool(findings),
            "findings": findings,
            "message": f"Found {len(findings)} leaked access key(s)" if findings else "No leaked keys",
        }

    if action == "invalidate_key":
        uname = payload.get("name") or ""
        kid = payload.get("access_key_id") or payload.get("id") or ""
        user = next((u for u in state.get("iamUsers", []) if u.get("name") == uname), None)
        if not user:
            return {"ok": False, "error": f"NoSuchEntity: The user with name {uname} cannot be found"}
        key = next((k for k in user.get("accessKeys") or [] if k.get("id") == kid), None)
        if not key:
            return {"ok": False, "error": f"NoSuchEntity: The Access Key with id {kid} cannot be found"}
        key["status"] = "Inactive"
        key["compromised"] = True
        inv = state.setdefault("invalidated_keys", [])
        if kid not in inv:
            inv.append(kid)
        _event(state, f"Access key {kid} invalidated (compromised)", "warning")
        _save(session_id, entry)
        return {
            "ok": True,
            "message": "Key invalidated — further use returns InvalidClientTokenId",
            "access_key": key,
        }

    if action == "rotate_access_key":
        # Zero-downtime dual-key overlap (X5a): create second Active key; old stays Active.
        uname = payload.get("name") or ""
        user = next((u for u in state.get("iamUsers", []) if u.get("name") == uname), None)
        if not user:
            return {"ok": False, "error": f"NoSuchEntity: The user with name {uname} cannot be found"}
        keys = user.setdefault("accessKeys", [])
        if not keys:
            return {"ok": False, "error": "No access key to rotate — create one first"}
        if len(keys) >= 2:
            return {
                "ok": False,
                "error": (
                    "LimitExceeded: Dual-key overlap already in place (2 keys). "
                    "Verify the old key is unused, then deactivate and delete it."
                ),
            }
        old = keys[0]
        new = {
            "id": payload.get("access_key_id") or new_access_key_id(),
            "created": _now_iso(),
            "status": "Active",
            "lastUsed": "N/A",
        }
        keys.append(new)
        _event(state, f"Access key rotated for {uname} (dual-key overlap)", "success")
        _save(session_id, entry)
        return {
            "ok": True,
            "message": "Dual-key rotation started — both keys Active",
            "old_access_key_id": old.get("id"),
            "new_access_key_id": new["id"],
            "access_keys": list(keys),
        }

    # ── S3 ─────────────────────────────────────────────────────────────────────
    if action == "create_bucket":
        name = (payload.get("name") or "").strip()
        if not name:
            return {"ok": False, "error": "Bucket name is required"}
        if any(b.get("name") == name for b in state.get("s3Buckets", [])):
            return {"ok": False, "error": f"BucketAlreadyExists: The requested bucket name '{name}' is not available"}
        block_public = payload.get("block_public", True)
        bucket = {
            "name": name, "region": payload.get("region") or region, "created": _now_iso(),
            "versioning": bool(payload.get("versioning")),
            "publicAccess": "Bucket and objects not public" if block_public else "Objects can be public",
            "encryption": payload.get("encryption") or "SSE-S3", "website": False,
            "objectOwnership": "Bucket owner enforced", "acl": "Private", "bucketPolicy": "", "cors": "",
            "lifecycleRules": [], "logging": False, "objects": [],
        }
        state.setdefault("s3Buckets", []).append(bucket)
        _event(state, f"Bucket {name} created", "success")
        _save(session_id, entry)
        return {"ok": True, "message": "CreateBucket succeeded"}

    if action == "delete_bucket":
        name = payload.get("name")
        bucket = next((b for b in state.get("s3Buckets", []) if b.get("name") == name), None)
        if not bucket:
            return {"ok": False, "error": f"NoSuchBucket: The specified bucket '{name}' does not exist"}
        if bucket.get("objects"):
            return {"ok": False, "error": "BucketNotEmpty: The bucket you tried to delete is not empty"}
        state["s3Buckets"] = [b for b in state["s3Buckets"] if b["name"] != name]
        _event(state, f"Bucket {name} deleted", "info")
        _save(session_id, entry)
        return {"ok": True, "message": "DeleteBucket succeeded"}

    if action == "update_bucket":
        name = payload.get("name")
        bucket = next((b for b in state.get("s3Buckets", []) if b.get("name") == name), None)
        if not bucket:
            return {"ok": False, "error": f"NoSuchBucket: The specified bucket '{name}' does not exist"}
        patch = payload.get("patch") or {}
        allowed = {"versioning", "publicAccess", "encryption", "website", "acl", "bucketPolicy", "logging"}
        for k, v in patch.items():
            if k in allowed:
                bucket[k] = v
        _event(state, f"Bucket {name} settings updated", "info")
        _save(session_id, entry)
        return {"ok": True, "message": "PutBucket* succeeded"}

    if action == "put_object":
        name = payload.get("bucket") or payload.get("name")
        bucket = next((b for b in state.get("s3Buckets", []) if b.get("name") == name), None)
        if not bucket:
            return {"ok": False, "error": f"NoSuchBucket: The specified bucket '{name}' does not exist"}
        key = payload.get("key") or ""
        if not key:
            return {"ok": False, "error": "Object key is required"}
        storage = (payload.get("storage_class") or payload.get("storageClass") or "STANDARD").upper()
        bucket["objects"] = [o for o in bucket.get("objects", []) if o.get("key") != key]
        bucket["objects"].append({
            "key": key,
            "size": int(payload.get("size") or 0),
            "modified": _now_iso(),
            "storageClass": storage,
        })
        _event(state, f"Uploaded {key} to {name}", "info")
        _save(session_id, entry)
        return {"ok": True, "message": "PutObject succeeded"}

    if action in ("put_bucket_lifecycle", "put_lifecycle_configuration"):
        name = payload.get("bucket") or payload.get("name")
        bucket = next((b for b in state.get("s3Buckets", []) if b.get("name") == name), None)
        if not bucket:
            return {"ok": False, "error": f"NoSuchBucket: The specified bucket '{name}' does not exist"}
        rules = payload.get("rules") or payload.get("lifecycleRules") or []
        if isinstance(rules, dict):
            rules = [rules]
        if not rules and payload.get("transition_days") is not None:
            rules = [{
                "id": payload.get("id") or "to-glacier",
                "status": "Enabled",
                "transitions": [{
                    "days": int(payload.get("transition_days") or 30),
                    "storageClass": payload.get("storage_class") or "GLACIER",
                }],
                "abortIncompleteMultipartUpload": {
                    "daysAfterInitiation": int(payload.get("abort_multipart_days") or 7),
                },
            }]
        bucket["lifecycleRules"] = list(rules)
        # Apply transitions to existing objects whose age exceeds rule days (teaching: age=modified days).
        for obj in bucket.get("objects") or []:
            for rule in rules:
                if str(rule.get("status") or "Enabled").lower() != "enabled":
                    continue
                for tr in rule.get("transitions") or []:
                    days = int(tr.get("days") or 0)
                    age = int(payload.get("object_age_days") or days + 1)
                    if age >= days:
                        obj["storageClass"] = str(tr.get("storageClass") or "GLACIER").upper()
        _event(state, f"Lifecycle configuration put on {name}", "success")
        _save(session_id, entry)
        return {
            "ok": True,
            "message": "PutBucketLifecycleConfiguration succeeded",
            "lifecycleRules": bucket["lifecycleRules"],
        }

    if action == "create_multipart_upload":
        name = payload.get("bucket") or payload.get("name")
        bucket = next((b for b in state.get("s3Buckets", []) if b.get("name") == name), None)
        if not bucket:
            return {"ok": False, "error": f"NoSuchBucket: The specified bucket '{name}' does not exist"}
        key = payload.get("key") or ""
        if not key:
            return {"ok": False, "error": "Object key is required"}
        upload_id = payload.get("upload_id") or f"mpu-{_hex(16)}"
        mpu = {
            "uploadId": upload_id,
            "key": key,
            "initiated": _now_iso(),
            "size": int(payload.get("size") or payload.get("parts_size") or 0),
            "status": "in_progress",
        }
        bucket.setdefault("multipartUploads", []).append(mpu)
        _event(state, f"Multipart upload started {upload_id} for {key}", "info")
        _save(session_id, entry)
        return {"ok": True, "message": "CreateMultipartUpload succeeded", "upload_id": upload_id}

    if action == "abort_multipart_upload":
        name = payload.get("bucket") or payload.get("name")
        bucket = next((b for b in state.get("s3Buckets", []) if b.get("name") == name), None)
        if not bucket:
            return {"ok": False, "error": f"NoSuchBucket: The specified bucket '{name}' does not exist"}
        uid = payload.get("upload_id") or payload.get("id") or ""
        before = len(bucket.get("multipartUploads") or [])
        bucket["multipartUploads"] = [
            m for m in (bucket.get("multipartUploads") or []) if m.get("uploadId") != uid
        ]
        if len(bucket.get("multipartUploads") or []) == before:
            return {"ok": False, "error": f"NoSuchUpload: Upload {uid} not found"}
        _event(state, f"Multipart upload {uid} aborted", "info")
        _save(session_id, entry)
        return {"ok": True, "message": "AbortMultipartUpload succeeded"}

    if action == "complete_multipart_upload":
        name = payload.get("bucket") or payload.get("name")
        bucket = next((b for b in state.get("s3Buckets", []) if b.get("name") == name), None)
        if not bucket:
            return {"ok": False, "error": f"NoSuchBucket: The specified bucket '{name}' does not exist"}
        uid = payload.get("upload_id") or payload.get("id") or ""
        mpu = next(
            (m for m in (bucket.get("multipartUploads") or []) if m.get("uploadId") == uid),
            None,
        )
        if not mpu:
            return {"ok": False, "error": f"NoSuchUpload: Upload {uid} not found"}
        key = mpu.get("key") or payload.get("key") or ""
        bucket["objects"] = [o for o in bucket.get("objects", []) if o.get("key") != key]
        bucket["objects"].append({
            "key": key,
            "size": int(mpu.get("size") or payload.get("size") or 0),
            "modified": _now_iso(),
            "storageClass": "STANDARD",
        })
        bucket["multipartUploads"] = [
            m for m in (bucket.get("multipartUploads") or []) if m.get("uploadId") != uid
        ]
        _save(session_id, entry)
        return {"ok": True, "message": "CompleteMultipartUpload succeeded", "key": key}

    if action in ("estimate_s3_storage_cost", "get_s3_storage_cost"):
        name = payload.get("bucket") or payload.get("name")
        buckets = state.get("s3Buckets") or []
        if name:
            buckets = [b for b in buckets if b.get("name") == name]
        # Teaching rates $/GB-month.
        rates = {
            "STANDARD": 0.023,
            "STANDARD_IA": 0.0125,
            "GLACIER": 0.004,
            "DEEP_ARCHIVE": 0.00099,
        }
        mpu_rate = 0.023  # incomplete multipart billed as Standard
        lines = []
        total = 0.0
        for b in buckets:
            by_class: dict[str, float] = {}
            for obj in b.get("objects") or []:
                sc = str(obj.get("storageClass") or "STANDARD").upper()
                by_class[sc] = by_class.get(sc, 0.0) + float(obj.get("size") or 0) / (1024 ** 3)
            for sc, gb in by_class.items():
                amt = round(gb * float(rates.get(sc) or rates["STANDARD"]), 4)
                total += amt
                lines.append({
                    "bucket": b.get("name"), "storageClass": sc, "gb": round(gb, 4), "amount": amt,
                })
            for mpu in b.get("multipartUploads") or []:
                if mpu.get("status") == "completed":
                    continue
                gb = float(mpu.get("size") or 0) / (1024 ** 3)
                amt = round(gb * mpu_rate, 4)
                total += amt
                lines.append({
                    "bucket": b.get("name"),
                    "storageClass": "INCOMPLETE_MULTIPART",
                    "uploadId": mpu.get("uploadId"),
                    "gb": round(gb, 4),
                    "amount": amt,
                })
            if not (b.get("lifecycleRules") or []):
                lines.append({
                    "bucket": b.get("name"),
                    "warning": "No lifecycle rules — petabyte-scale Standard retention risk",
                })
        return {
            "ok": True,
            "message": "S3 storage cost estimate",
            "total": round(total, 4),
            "lines": lines,
        }

    if action == "delete_object":
        name = payload.get("bucket") or payload.get("name")
        bucket = next((b for b in state.get("s3Buckets", []) if b.get("name") == name), None)
        if not bucket:
            return {"ok": False, "error": f"NoSuchBucket: The specified bucket '{name}' does not exist"}
        key = payload.get("key")
        bucket["objects"] = [o for o in bucket.get("objects", []) if o.get("key") != key]
        _event(state, f"Deleted {key} from {name}", "info")
        _save(session_id, entry)
        return {"ok": True, "message": "DeleteObject succeeded"}

    # ── IAM ────────────────────────────────────────────────────────────────────
    if action == "create_iam_user":
        uname = (payload.get("name") or "").strip()
        if not uname:
            return {"ok": False, "error": "User name is required"}
        if any(u.get("name") == uname for u in state.get("iamUsers", [])):
            return {"ok": False, "error": f"EntityAlreadyExists: User with name {uname} already exists"}
        user = {"id": new_iam_user_id(), "name": uname, "created": _now_iso(), "consoleAccess": bool(payload.get("console_access")), "groups": [], "policies": list(payload.get("policies") or []), "accessKeys": []}
        state.setdefault("iamUsers", []).append(user)
        _event(state, f"IAM user {uname} created", "success")
        _save(session_id, entry)
        return {"ok": True, "message": "CreateUser succeeded", "user_id": user["id"]}

    if action == "attach_user_policy":
        uname = payload.get("name")
        user = next((u for u in state.get("iamUsers", []) if u.get("name") == uname), None)
        if not user:
            return {"ok": False, "error": f"NoSuchEntity: The user with name {uname} cannot be found"}
        policy = payload.get("policy")
        if policy and policy not in user.setdefault("policies", []):
            user["policies"].append(policy)
        _event(state, f"Policy {policy} attached to {uname}", "info")
        _save(session_id, entry)
        return {"ok": True, "message": "AttachUserPolicy succeeded"}

    if action == "create_iam_role":
        rname = (payload.get("name") or "").strip()
        if not rname:
            return {"ok": False, "error": "Role name is required"}
        role = {"id": new_iam_role_id(), "name": rname, "created": _now_iso(), "trustedEntity": payload.get("trusted_entity") or "ec2.amazonaws.com", "policies": list(payload.get("policies") or [])}
        state.setdefault("iamRoles", []).append(role)
        _event(state, f"IAM role {rname} created", "success")
        _save(session_id, entry)
        return {"ok": True, "message": "CreateRole succeeded", "role_id": role["id"]}

    if action == "create_iam_policy":
        pname = (payload.get("name") or "").strip()
        if not pname:
            return {"ok": False, "error": "Policy name is required"}
        pol = {"name": pname, "type": "Customer managed", "attached": 0, "created": _now_iso(), "description": payload.get("description") or "", "document": payload.get("document") or {"Version": "2012-10-17", "Statement": []}}
        state.setdefault("iamPolicies", []).append(pol)
        _event(state, f"IAM policy {pname} created", "success")
        _save(session_id, entry)
        return {"ok": True, "message": "CreatePolicy succeeded"}

    if action == "update_iam_policy":
        pname = payload.get("name") or ""
        pol = next((p for p in state.get("iamPolicies", []) if p.get("name") == pname), None)
        if not pol:
            return {"ok": False, "error": f"NoSuchEntity: The policy with name {pname} cannot be found"}
        patch = payload.get("patch") or {}
        for k, v in patch.items():
            if k in ("description", "document", "attached"):
                pol[k] = v
        _event(state, f"IAM policy {pname} updated", "info")
        _save(session_id, entry)
        return {"ok": True, "message": "CreatePolicyVersion succeeded"}

    if action == "delete_iam_policy":
        pname = payload.get("name") or ""
        before = len(state.get("iamPolicies") or [])
        state["iamPolicies"] = [p for p in (state.get("iamPolicies") or []) if p.get("name") != pname]
        if len(state.get("iamPolicies") or []) == before:
            return {"ok": False, "error": f"NoSuchEntity: The policy with name {pname} cannot be found"}
        _event(state, f"IAM policy {pname} deleted", "info")
        _save(session_id, entry)
        return {"ok": True, "message": "DeletePolicy succeeded"}

    if action == "analyze_policy_scope":
        pname = payload.get("name") or payload.get("policy") or ""
        pol = next((p for p in state.get("iamPolicies") or [] if p.get("name") == pname), None)
        if not pol:
            return {"ok": False, "error": f"NoSuchEntity: The policy with name {pname} cannot be found"}
        doc = pol.get("document") if isinstance(pol.get("document"), dict) else {}
        findings = []
        for stmt in doc.get("Statement") or []:
            actions = stmt.get("Action") or []
            if isinstance(actions, str):
                actions = [actions]
            resources = stmt.get("Resource") or []
            if isinstance(resources, str):
                resources = [resources]
            if "*" in actions or "Action" in stmt and stmt.get("Action") == "*":
                findings.append({"severity": "CRITICAL", "issue": "Action=* grants every API"})
            if any(a.endswith(":*") for a in actions):
                findings.append({"severity": "HIGH", "issue": f"Service-wide wildcard in {actions}"})
            if "*" in resources:
                findings.append({"severity": "HIGH", "issue": "Resource=* is not least privilege"})
        excessive = bool(findings)
        return {
            "ok": True,
            "policy": pname,
            "excessive": excessive,
            "findings": findings,
            "message": (
                "Policy is overly broad — tighten before production"
                if excessive else "Policy scope looks constrained"
            ),
        }

    if action == "tighten_policy":
        # Cut Action=* to an allow-list without inventing resources the caller needs.
        pname = payload.get("name") or payload.get("policy") or ""
        pol = next((p for p in state.get("iamPolicies") or [] if p.get("name") == pname), None)
        if not pol:
            return {"ok": False, "error": f"NoSuchEntity: The policy with name {pname} cannot be found"}
        actions = payload.get("actions") or [
            "s3:GetObject", "s3:PutObject", "s3:ListBucket",
            "ec2:DescribeInstances", "logs:CreateLogStream", "logs:PutLogEvents",
        ]
        if isinstance(actions, str):
            actions = [a.strip() for a in actions.split(",") if a.strip()]
        resource = payload.get("resource") or payload.get("resources") or [
            "arn:aws:s3:::my-web-assets-demo-123456",
            "arn:aws:s3:::my-web-assets-demo-123456/*",
        ]
        if isinstance(resource, str):
            resource = [resource]
        pol["document"] = {
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Action": list(actions),
                "Resource": list(resource),
            }],
        }
        pol["description"] = payload.get("description") or "Least-privilege tightened policy"
        _event(state, f"IAM policy {pname} tightened to {len(actions)} action(s)", "success")
        _save(session_id, entry)
        return {"ok": True, "message": "Policy tightened to least privilege", "policy": pol}

    if action == "invoke_with_policy":
        # Prove the caller still works after tighten (required APIs subset of policy).
        pname = payload.get("name") or payload.get("policy") or ""
        pol = next((p for p in state.get("iamPolicies") or [] if p.get("name") == pname), None)
        if not pol:
            return {"ok": False, "error": f"NoSuchEntity: The policy with name {pname} cannot be found"}
        required = payload.get("required_actions") or payload.get("actions") or []
        if isinstance(required, str):
            required = [a.strip() for a in required.split(",") if a.strip()]
        allowed: list[str] = []
        for stmt in (pol.get("document") or {}).get("Statement") or []:
            if str(stmt.get("Effect") or "Allow").lower() != "allow":
                continue
            acts = stmt.get("Action") or []
            if isinstance(acts, str):
                acts = [acts]
            allowed.extend(str(a) for a in acts)
        if "*" in allowed:
            missing = []
        else:
            missing = []
            for need in required:
                ok_act = any(
                    a == need or (a.endswith("*") and need.startswith(a[:-1]))
                    for a in allowed
                )
                if not ok_act:
                    missing.append(need)
        if missing:
            return {
                "ok": False,
                "error": f"AccessDenied: missing actions {missing}",
                "missing": missing,
            }
        return {
            "ok": True,
            "message": "Caller succeeded with tightened policy",
            "allowed": allowed,
        }

    if action in ("create_log_group", "put_log_group"):
        name = (payload.get("name") or payload.get("log_group") or "").strip()
        if not name:
            return {"ok": False, "error": "Log group name required"}
        groups = state.setdefault("logGroups", [])
        existing = next((g for g in groups if g.get("name") == name), None)
        if existing:
            if "log_level" in payload or "logLevel" in payload:
                existing["logLevel"] = (
                    payload.get("log_level") or payload.get("logLevel") or existing.get("logLevel")
                ).upper()
            if "retention_days" in payload or "retentionDays" in payload:
                existing["retentionDays"] = int(
                    payload.get("retention_days") or payload.get("retentionDays") or 30
                )
            if "ingested_gb_per_day" in payload:
                existing["ingestedGbPerDay"] = float(payload["ingested_gb_per_day"])
            group = existing
            msg = f"Updated log group {name}"
        else:
            group = {
                "name": name,
                "region": region,
                "retentionDays": int(payload.get("retention_days") or payload.get("retentionDays") or 30),
                "logLevel": str(payload.get("log_level") or payload.get("logLevel") or "INFO").upper(),
                "ingestedGbPerDay": float(payload.get("ingested_gb_per_day") or 1.0),
            }
            groups.append(group)
            msg = f"Created log group {name}"
        _save(session_id, entry)
        return {"ok": True, "message": msg, "log_group": group}

    if action == "set_log_level":
        name = payload.get("name") or payload.get("log_group") or ""
        group = next((g for g in state.get("logGroups") or [] if g.get("name") == name), None)
        if not group:
            return {"ok": False, "error": f"ResourceNotFoundException: log group {name}"}
        level = str(payload.get("log_level") or payload.get("level") or "INFO").upper()
        old = group.get("logLevel")
        group["logLevel"] = level
        # Debug→Info typically cuts volume ~10× in teaching model.
        if old == "DEBUG" and level in ("INFO", "WARN", "ERROR"):
            group["ingestedGbPerDay"] = round(float(group.get("ingestedGbPerDay") or 0) / 10.0, 4)
        elif level == "DEBUG" and old != "DEBUG":
            group["ingestedGbPerDay"] = round(float(group.get("ingestedGbPerDay") or 0) * 10.0, 4)
        _event(state, f"Log group {name} level {old}→{level}", "info")
        _save(session_id, entry)
        return {"ok": True, "message": f"Log level set to {level}", "log_group": group}

    if action in ("estimate_log_ingestion_cost", "get_log_ingestion_cost"):
        # CloudWatch Logs ingestion ~$0.50/GB teaching rate.
        rate = float(payload.get("rate_per_gb") or 0.50)
        days = float(payload.get("days") or 30)
        lines = []
        total = 0.0
        for g in state.get("logGroups") or []:
            gb_day = float(g.get("ingestedGbPerDay") or 0)
            amt = round(gb_day * days * rate, 4)
            total += amt
            lines.append({
                "log_group": g.get("name"),
                "logLevel": g.get("logLevel"),
                "gb_per_day": gb_day,
                "amount": amt,
                "warning": (
                    "DEBUG level left on in production — high ingestion cost"
                    if str(g.get("logLevel") or "").upper() == "DEBUG" else None
                ),
            })
        return {
            "ok": True,
            "message": "CloudWatch Logs ingestion estimate",
            "total": round(total, 4),
            "days": days,
            "lines": lines,
        }

    if action in ("purchase_reserved_instance", "purchase_ri"):
        itype = payload.get("instance_type") or payload.get("type") or "t3.medium"
        count = int(payload.get("count") or 1)
        term_months = int(payload.get("term_months") or 12)
        # Teaching: RI hourly ≈ 60% of on-demand.
        od = float(get_instance_type(itype).get("hourlyUsd") or 0.04)
        ri_hourly = round(od * 0.6, 4)
        row = {
            "id": payload.get("id") or f"ri-{_hex(8)}",
            "instanceType": itype,
            "count": count,
            "termMonths": term_months,
            "hourlyUsd": ri_hourly,
            "onDemandHourlyUsd": od,
            "state": "active",
        }
        state.setdefault("reservedInstances", []).append(row)
        _save(session_id, entry)
        return {"ok": True, "message": "PurchaseReservedInstancesOffering succeeded", "ri": row}

    if action in ("purchase_savings_plan", "create_savings_plan"):
        commit = float(payload.get("hourly_commitment") or payload.get("commitment") or 1.0)
        row = {
            "id": payload.get("id") or f"sp-{_hex(8)}",
            "hourlyCommitment": commit,
            "discount": float(payload.get("discount") or 0.28),  # ~28% compute SP
            "state": "active",
        }
        state.setdefault("savingsPlans", []).append(row)
        _save(session_id, entry)
        return {"ok": True, "message": "CreateSavingsPlan succeeded", "savings_plan": row}

    if action in ("analyze_ri_sp_coverage", "get_ri_sp_coverage"):
        hours = float(payload.get("hours") or 24)
        running = [
            i for i in (state.get("instances") or [])
            if i.get("state") in ("running", "pending")
        ]
        # On-demand spend for running fleet.
        od_total = 0.0
        by_type: dict[str, int] = {}
        for inst in running:
            t = str(inst.get("type") or "t2.micro")
            by_type[t] = by_type.get(t, 0) + 1
            od_total += float(get_instance_type(t).get("hourlyUsd") or 0.0116) * hours

        # Cover with RIs first (per type), then SP dollar commitment.
        covered_od = 0.0
        ri_lines = []
        remaining = dict(by_type)
        for ri in state.get("reservedInstances") or []:
            if ri.get("state") != "active":
                continue
            t = str(ri.get("instanceType") or "")
            count = int(ri.get("count") or 0)
            use = min(count, remaining.get(t, 0))
            remaining[t] = remaining.get(t, 0) - use
            od_rate = float(ri.get("onDemandHourlyUsd") or get_instance_type(t).get("hourlyUsd") or 0)
            ri_rate = float(ri.get("hourlyUsd") or od_rate * 0.6)
            covered_od += od_rate * use * hours
            ri_lines.append({
                "type": t, "covered": use, "ri_hourly": ri_rate,
                "savings": round((od_rate - ri_rate) * use * hours, 4),
            })

        uncovered_od = 0.0
        for t, n in remaining.items():
            if n <= 0:
                continue
            uncovered_od += float(get_instance_type(t).get("hourlyUsd") or 0) * n * hours

        sp_commit = sum(
            float(s.get("hourlyCommitment") or 0) * hours
            for s in (state.get("savingsPlans") or [])
            if s.get("state") == "active"
        )
        sp_discount = 0.28
        for s in state.get("savingsPlans") or []:
            if s.get("state") == "active":
                sp_discount = float(s.get("discount") or 0.28)
                break
        sp_applied = min(sp_commit, uncovered_od)
        sp_savings = round(sp_applied * sp_discount, 4)
        still_od = uncovered_od - sp_applied

        effective = round(od_total - sum(r["savings"] for r in ri_lines) - sp_savings, 4)
        coverage_pct = round(100.0 * (1.0 - (still_od / od_total)), 1) if od_total else 100.0
        return {
            "ok": True,
            "message": "RI/SP coverage analysis",
            "on_demand_usd": round(od_total, 4),
            "effective_usd": max(0.0, effective),
            "coverage_percent": max(0.0, min(100.0, coverage_pct)),
            "ri_lines": ri_lines,
            "sp_applied_usd": round(sp_applied, 4),
            "sp_savings_usd": sp_savings,
            "uncovered_on_demand_usd": round(still_od, 4),
            "hours": hours,
        }

    if action == "attach_instance_role":
        ident = payload.get("instance_id") or payload.get("id")
        inst = _find_instance(state, ident)
        if not inst:
            return {"ok": False, "error": f"The instance ID '{ident}' does not exist"}
        role = payload.get("role") or ""
        if role and not any(r.get("name") == role for r in state.get("iamRoles", [])):
            return {"ok": False, "error": f"NoSuchEntity: Instance profile {role} not found"}
        inst["iamRole"] = role
        _event(state, f"Role {role} attached to {inst.get('id')}", "info")
        _save(session_id, entry)
        return {"ok": True, "message": "AssociateIamInstanceProfile succeeded"}

    if action == "set_region":
        state["region"] = payload.get("region") or region
        _save(session_id, entry)
        return {"ok": True, "message": f"Region set to {state['region']}"}

    if action == "assume_role":
        # Trust-aware STS (X5a). Handled here so the permissive v2 façade never runs.
        role_name = (
            payload.get("role") or payload.get("role_name") or payload.get("name") or ""
        ).strip()
        if not role_name:
            return {"ok": False, "error": "Role name required"}
        role = next(
            (r for r in state.get("iamRoles") or []
             if r.get("name") == role_name or r.get("arn") == role_name),
            None,
        )
        if not role:
            return {
                "ok": False,
                "error": (
                    f"AccessDenied: User is not authorized to perform: sts:AssumeRole "
                    f"on resource: {role_name}"
                ),
            }
        principal = (
            payload.get("principal")
            or payload.get("caller_arn")
            or payload.get("source_account")
            or ""
        ).strip()
        trusted = str(role.get("trustedEntity") or "")
        trust_doc = role.get("trust_policy") if isinstance(role.get("trust_policy"), dict) else {}
        principals: list[str] = []
        for stmt in trust_doc.get("Statement") or []:
            p = (stmt.get("Principal") or {})
            if isinstance(p, dict):
                aws_p = p.get("AWS")
                if isinstance(aws_p, list):
                    principals.extend(str(x) for x in aws_p)
                elif aws_p:
                    principals.append(str(aws_p))
                svc = p.get("Service")
                if svc:
                    principals.append(str(svc))
        if trusted:
            principals.append(trusted)
        ok_principal = False
        if not principals:
            ok_principal = True
        elif principal:
            ok_principal = any(
                principal == t
                or principal.endswith(t)
                or t.endswith(principal)
                or (":" not in t and t in principal)
                for t in principals
            )
        else:
            # No principal: allow only service-style trustedEntity (EC2/Lambda profiles).
            ok_principal = any("." in t and "arn:" not in t for t in principals)
        if not ok_principal:
            return {
                "ok": False,
                "error": (
                    "AccessDenied: User is not authorized to perform: sts:AssumeRole. "
                    "The trust policy does not allow this principal."
                ),
            }
        want_ext = role.get("external_id")
        if not want_ext:
            for stmt in trust_doc.get("Statement") or []:
                cond = (stmt.get("Condition") or {}).get("StringEquals") or {}
                want_ext = cond.get("sts:ExternalId") or want_ext
        got_ext = payload.get("external_id") or payload.get("ExternalId")
        if want_ext and str(got_ext or "") != str(want_ext):
            return {
                "ok": False,
                "error": (
                    "AccessDenied: User is not authorized to perform: sts:AssumeRole. "
                    "Missing or incorrect ExternalId."
                ),
            }
        session_name = payload.get("session_name") or "fixitlab-session"
        assumed = {
            "role": role.get("name"),
            "session_name": session_name,
            "arn": (
                payload.get("arn")
                or f"arn:aws:sts::{ACCOUNT_ID}:assumed-role/{role.get('name')}/{session_name}"
            ),
            "assumed_at": _now_iso(),
            "external_id_ok": True,
        }
        state.setdefault("sts", {})["assumed_role"] = assumed
        _event(state, f"Assumed role {role.get('name')}", "success")
        _save(session_id, entry)
        return {"ok": True, "message": f"Assumed role {role.get('name')}", "sts": assumed}

    if action == "set_org_policy":
        policies = state.setdefault("org_policies", {})
        if "require_ebs_encryption" in payload:
            policies["require_ebs_encryption"] = bool(payload.get("require_ebs_encryption"))
        if "required_tags" in payload:
            tags = payload.get("required_tags") or []
            if isinstance(tags, str):
                tags = [t.strip() for t in tags.split(",") if t.strip()]
            policies["required_tags"] = [str(t) for t in tags]
        _event(state, f"Org policy updated: {policies}", "info")
        _save(session_id, entry)
        return {"ok": True, "message": "Org policy updated", "org_policies": policies}

    if action in ("get_cost_and_usage", "ce_get_cost_and_usage", "estimate_cost"):
        hours = float(payload.get("hours") or payload.get("period_hours") or 24)
        usage = estimate_cost_and_usage(state, hours=hours)
        return {"ok": True, "message": "GetCostAndUsage", **usage}

    if action == "create_oidc_provider":
        url = (
            payload.get("url")
            or payload.get("provider")
            or "oidc.eks.us-east-1.amazonaws.com/id/EXAMPLED429"
        ).strip().removeprefix("https://")
        providers = state.setdefault("oidcProviders", [])
        if any(p.get("url") == url for p in providers):
            return {"ok": False, "error": f"EntityAlreadyExists: OIDC provider {url}"}
        row = {
            "arn": f"arn:aws:iam::{ACCOUNT_ID}:oidc-provider/{url}",
            "url": url,
            "client_ids": list(payload.get("client_ids") or ["sts.amazonaws.com"]),
            "created": _now_iso(),
        }
        providers.append(row)
        _event(state, f"OIDC provider {url} created", "success")
        _save(session_id, entry)
        return {"ok": True, "message": "CreateOpenIDConnectProvider succeeded", "provider": row}

    if action == "assume_role_with_web_identity":
        role_name = (
            payload.get("role") or payload.get("role_name") or payload.get("name") or ""
        ).strip()
        if not role_name:
            return {"ok": False, "error": "Role name required"}
        role = next(
            (r for r in state.get("iamRoles") or []
             if r.get("name") == role_name or r.get("arn") == role_name),
            None,
        )
        if not role:
            return {
                "ok": False,
                "error": f"AccessDenied: sts:AssumeRoleWithWebIdentity on {role_name}",
            }
        token = payload.get("web_identity_token") or payload.get("token") or {}
        if isinstance(token, str):
            # Teaching tokens are "sub=<sa>" or JSON-ish; accept bare sub strings.
            token = {"sub": token} if token else {}
        if not isinstance(token, dict):
            token = {}
        sub = str(
            token.get("sub")
            or payload.get("sub")
            or payload.get("service_account")
            or ""
        ).strip()
        want_sub = str(role.get("oidc_sub") or "")
        trust = role.get("trust_policy") if isinstance(role.get("trust_policy"), dict) else {}
        for stmt in trust.get("Statement") or []:
            cond = (stmt.get("Condition") or {}).get("StringEquals") or {}
            for k, v in cond.items():
                if str(k).endswith(":sub"):
                    want_sub = str(v)
        provider_url = str(role.get("oidc_provider") or "")
        providers = state.get("oidcProviders") or []
        if provider_url and not any(p.get("url") == provider_url for p in providers):
            return {
                "ok": False,
                "error": (
                    "InvalidIdentityToken: No OIDC provider registered for "
                    f"{provider_url}. CreateOpenIDConnectProvider first."
                ),
            }
        if want_sub and sub != want_sub:
            return {
                "ok": False,
                "error": (
                    "AccessDenied: sts:AssumeRoleWithWebIdentity — token sub "
                    f"does not match trust policy (want {want_sub!r})."
                ),
            }
        session_name = payload.get("session_name") or "irsa-session"
        assumed = {
            "role": role.get("name"),
            "session_name": session_name,
            "arn": f"arn:aws:sts::{ACCOUNT_ID}:assumed-role/{role.get('name')}/{session_name}",
            "assumed_at": _now_iso(),
            "web_identity": True,
            "sub": sub,
        }
        state.setdefault("sts", {})["assumed_role"] = assumed
        _event(state, f"Assumed role {role.get('name')} via web identity", "success")
        _save(session_id, entry)
        return {
            "ok": True,
            "message": f"Assumed role {role.get('name')} with web identity",
            "sts": assumed,
        }

    if action == "migrate_user_to_irsa":
        # Deactivate long-lived access keys after IRSA is proven working.
        uname = payload.get("name") or payload.get("user") or ""
        user = next((u for u in state.get("iamUsers", []) if u.get("name") == uname), None)
        if not user:
            return {"ok": False, "error": f"NoSuchEntity: The user with name {uname} cannot be found"}
        if not (state.get("sts") or {}).get("assumed_role", {}).get("web_identity"):
            return {
                "ok": False,
                "error": (
                    "ValidationError: Prove AssumeRoleWithWebIdentity works before "
                    "revoking static access keys."
                ),
            }
        deactivated = []
        for key in user.get("accessKeys") or []:
            if key.get("status") == "Active":
                key["status"] = "Inactive"
                deactivated.append(key.get("id"))
        _event(state, f"Migrated {uname} to IRSA; deactivated keys {deactivated}", "success")
        _save(session_id, entry)
        return {
            "ok": True,
            "message": "Static keys deactivated after IRSA migration",
            "deactivated_keys": deactivated,
        }

    if action in ("create_budget", "put_budget"):
        # Prefer engine budgets (with kill-switch) over the cosmetic v2 façade.
        name = (payload.get("name") or f"budget-{_hex(4)}").strip()
        budgets = state.setdefault("budgets", [])
        existing = next((b for b in budgets if b.get("name") == name), None)
        amount = float(payload.get("amount") or payload.get("limit") or 100)
        if existing:
            existing["amount"] = amount
            if "kill_switch" in payload:
                existing["kill_switch"] = bool(payload.get("kill_switch"))
            budget = existing
            msg = f"Updated budget {name}"
        else:
            budget = {
                "id": payload.get("id") or f"budget-{_hex(8)}",
                "name": name,
                "amount": amount,
                "actual": 0.0,
                "status": "OK",
                "kill_switch": bool(payload.get("kill_switch", True)),
                "protect_environments": list(
                    payload.get("protect_environments")
                    or ["production", "prod"]
                ),
            }
            budgets.append(budget)
            msg = f"Created budget {name}"
        _event(state, msg, "success")
        _save(session_id, entry)
        return {"ok": True, "message": msg, "budget": budget}

    if action in ("evaluate_budget", "check_budget"):
        hours = float(payload.get("hours") or 24)
        usage = estimate_cost_and_usage(state, hours=hours)
        name = payload.get("name") or payload.get("budget")
        budgets = state.setdefault("budgets", [])
        targets = [b for b in budgets if not name or b.get("name") == name]
        if not targets:
            return {"ok": False, "error": "No budget found — create_budget first"}
        results = []
        for b in targets:
            b["actual"] = usage["total"]
            exceeded = usage["total"] > float(b.get("amount") or 0)
            b["status"] = "EXCEEDED" if exceeded else "OK"
            results.append({
                "name": b.get("name"),
                "amount": b.get("amount"),
                "actual": b["actual"],
                "status": b["status"],
                "kill_switch": bool(b.get("kill_switch")),
            })
        _save(session_id, entry)
        return {
            "ok": True,
            "message": "Budget evaluated against derived cost model",
            "usage": usage,
            "budgets": results,
        }

    if action in ("trigger_budget_kill_switch", "budget_kill_switch"):
        # Stop non-prod workloads only — never take production down (X5b judgement).
        hours = float(payload.get("hours") or 24)
        usage = estimate_cost_and_usage(state, hours=hours)
        name = payload.get("name") or payload.get("budget")
        budgets = state.setdefault("budgets", [])
        budget = next((b for b in budgets if not name or b.get("name") == name), None)
        if not budget:
            return {"ok": False, "error": "No budget found — create_budget first"}
        budget["actual"] = usage["total"]
        if usage["total"] <= float(budget.get("amount") or 0):
            budget["status"] = "OK"
            _save(session_id, entry)
            return {
                "ok": True,
                "message": "Budget OK — kill switch not armed",
                "stopped": [],
                "skipped_prod": [],
                "budget": budget,
            }
        budget["status"] = "EXCEEDED"
        if not budget.get("kill_switch", True):
            _save(session_id, entry)
            return {
                "ok": False,
                "error": "Budget exceeded but kill_switch is disabled on this budget",
                "budget": budget,
            }
        protect = {
            str(x).lower()
            for x in (budget.get("protect_environments") or ["production", "prod"])
        }
        stopped = []
        skipped_prod = []
        for inst in state.get("instances") or []:
            if inst.get("state") not in ("running", "pending"):
                continue
            env = str((inst.get("tags") or {}).get("Environment") or "").lower()
            if env in protect:
                skipped_prod.append(inst.get("id"))
                continue
            inst["state"] = "stopping"
            inst["_transition"] = {
                "state": "stopped",
                "at": _now() + STOPPING_SECONDS,
            }
            stopped.append(inst.get("id"))
        _event(
            state,
            f"Budget kill switch stopped {len(stopped)} non-prod; preserved {len(skipped_prod)} prod",
            "warning" if stopped else "info",
        )
        _save(session_id, entry)
        return {
            "ok": True,
            "message": (
                f"Kill switch armed: stopped {len(stopped)} non-prod instance(s); "
                f"preserved {len(skipped_prod)} production"
            ),
            "stopped": stopped,
            "skipped_prod": skipped_prod,
            "budget": budget,
            "usage": usage,
        }

    if action == "copy_snapshot":
        src = payload.get("snapshot_id") or payload.get("source_snapshot_id") or ""
        snap = next((s for s in state.get("snapshots") or [] if s.get("id") == src), None)
        if not snap:
            return {
                "ok": False,
                "error": f"InvalidSnapshot.NotFound: The snapshot '{src}' does not exist.",
            }
        encrypted = (
            bool(payload.get("encrypted")) if "encrypted" in payload else bool(snap.get("encrypted"))
        )
        kms_key = (payload.get("kms_key_id") or payload.get("kms_key") or "").strip()
        if kms_key:
            encrypted = True
        org = state.get("org_policies") or {}
        if org.get("require_ebs_encryption") and not encrypted:
            return {
                "ok": False,
                "error": (
                    "SnapshotCopyUnauthorized: Your organization requires EBS encryption. "
                    "Copy with Encrypted=true and a KMS key."
                ),
            }
        new_snap = {
            "id": payload.get("new_snapshot_id") or f"snap-{_hex(17)}",
            "region": payload.get("destination_region") or region,
            "volumeId": snap.get("volumeId"),
            "size": snap.get("size"),
            "state": "completed",
            "progress": "100%",
            "description": payload.get("description") or f"Copied from {src}",
            "started": _now_iso(),
            "encrypted": encrypted,
            "kmsKeyId": kms_key or None,
            "sourceSnapshotId": src,
        }
        state.setdefault("snapshots", []).append(new_snap)
        _event(state, f"Snapshot {src} copied → {new_snap['id']}", "success")
        _save(session_id, entry)
        return {
            "ok": True,
            "message": "CopySnapshot succeeded",
            "snapshot_id": new_snap["id"],
            "snapshot": new_snap,
        }

    if action == "list_orphaned_resources":
        volumes = [
            v for v in state.get("volumes") or []
            if v.get("state") == "available" and not v.get("attachedTo")
        ]
        snapshots = [s for s in state.get("snapshots") or [] if s.get("orphaned")]
        eips = [
            e for e in state.get("elasticIps") or []
            if not e.get("associationId") and not e.get("instanceId")
        ]
        return {
            "ok": True,
            "orphaned": {
                "volumes": volumes,
                "snapshots": snapshots,
                "elastic_ips": eips,
            },
        }

    if action in ("estimate_cross_az_transfer", "simulate_cross_az_traffic"):
        # Misplaced replica / chatty cross-AZ pairs → data-transfer charges (X5b).
        gb = float(payload.get("gb") or payload.get("gigabytes") or 100)
        rate = float(payload.get("rate_per_gb") or 0.01)  # teaching inter-AZ rate
        src_id = payload.get("source_instance") or payload.get("primary")
        dst_id = payload.get("dest_instance") or payload.get("replica")
        running = [
            i for i in (state.get("instances") or [])
            if i.get("state") in ("running", "pending")
        ]
        src = next((i for i in running if i.get("id") == src_id or i.get("name") == src_id), None)
        dst = next((i for i in running if i.get("id") == dst_id or i.get("name") == dst_id), None)
        if not src or not dst:
            # Auto-pick first two running instances in different AZs.
            by_az: dict[str, list] = {}
            for i in running:
                by_az.setdefault(str(i.get("az") or ""), []).append(i)
            azs = [a for a, rows in by_az.items() if a and rows]
            if len(azs) >= 2:
                src = by_az[azs[0]][0]
                dst = by_az[azs[1]][0]
        if not src or not dst:
            return {
                "ok": True,
                "message": "No cross-AZ pair found — $0 transfer",
                "cross_az_usd": 0.0,
                "same_az": True,
                "gb": gb,
            }
        same = str(src.get("az") or "") == str(dst.get("az") or "")
        if same:
            return {
                "ok": True,
                "message": (
                    f"{src.get('name') or src.get('id')} and "
                    f"{dst.get('name') or dst.get('id')} share AZ "
                    f"{src.get('az')} — no inter-AZ charge"
                ),
                "cross_az_usd": 0.0,
                "same_az": True,
                "gb": gb,
                "source": src.get("id"),
                "dest": dst.get("id"),
            }
        charge = round(gb * rate, 4)
        return {
            "ok": True,
            "message": (
                f"Cross-AZ transfer {src.get('az')}→{dst.get('az')}: ${charge} "
                f"({gb} GB × ${rate}/GB). Co-locate the replica to eliminate this."
            ),
            "cross_az_usd": charge,
            "same_az": False,
            "gb": gb,
            "source": src.get("id"),
            "dest": dst.get("id"),
            "source_az": src.get("az"),
            "dest_az": dst.get("az"),
        }

    if action in ("tick_asg_scaling", "simulate_asg_runaway"):
        ensure_v2(state)
        name = payload.get("name") or payload.get("id") or "web-asg"
        asgs = state.setdefault("autoScalingGroups", [])
        asg = next((a for a in asgs if a.get("name") == name or a.get("id") == name), None)
        if not asg:
            return {"ok": False, "error": f"Auto Scaling group '{name}' not found"}
        policy = asg.setdefault("scaling_policy", {
            "metric": "CPUUtilization",
            "threshold": 70,
            "cooldown_seconds": 300,
            "runaway": False,
        })
        if payload.get("runaway") is True or policy.get("runaway"):
            policy["runaway"] = True
            # Broken policy: threshold 0 + no cooldown → scales every tick to max.
            policy["threshold"] = int(policy.get("threshold") or 0)
            if int(policy.get("threshold") or 0) <= 0:
                policy["threshold"] = 0
            policy["cooldown_seconds"] = 0
        steps = max(1, int(payload.get("ticks") or 1))
        history = asg.setdefault("scaling_history", [])
        for _ in range(steps):
            desired = int(asg.get("desired") or 0)
            mx = int(asg.get("max") or desired)
            # Runaway / always-alarm: scale out one instance per tick until max.
            metric = float(payload.get("metric_value") or (100 if policy.get("runaway") else 50))
            threshold = float(policy.get("threshold") or 70)
            cooldown = int(policy.get("cooldown_seconds") or 0)
            if cooldown > 0 and history and not policy.get("runaway"):
                # Cooldown blocks further scale-out (teaching simplification).
                break
            if metric >= threshold and desired < mx:
                asg["desired"] = desired + 1
                history.append({
                    "at": _now_iso(),
                    "action": "scale_out",
                    "desired": asg["desired"],
                    "metric": metric,
                })
            elif metric < threshold and desired > int(asg.get("min") or 0):
                asg["desired"] = desired - 1
                history.append({
                    "at": _now_iso(),
                    "action": "scale_in",
                    "desired": asg["desired"],
                    "metric": metric,
                })
        runaway = (
            bool(policy.get("runaway"))
            or (int(policy.get("threshold") or 70) <= 0 and int(policy.get("cooldown_seconds") or 0) == 0)
        )
        at_max = int(asg.get("desired") or 0) >= int(asg.get("max") or 0)
        _save(session_id, entry)
        return {
            "ok": True,
            "message": (
                f"ASG {asg.get('name')} desired={asg.get('desired')}"
                + (" (runaway — hit max)" if runaway and at_max else "")
            ),
            "asg": asg,
            "runaway": runaway and at_max,
        }

    if action == "fix_asg_scaling_policy":
        ensure_v2(state)
        name = payload.get("name") or payload.get("id") or "web-asg"
        asgs = state.setdefault("autoScalingGroups", [])
        asg = next((a for a in asgs if a.get("name") == name or a.get("id") == name), None)
        if not asg:
            return {"ok": False, "error": f"Auto Scaling group '{name}' not found"}
        policy = asg.setdefault("scaling_policy", {})
        policy["runaway"] = False
        policy["threshold"] = int(payload.get("threshold") or 70)
        policy["cooldown_seconds"] = int(payload.get("cooldown_seconds") or 300)
        policy["metric"] = payload.get("metric") or "CPUUtilization"
        if "desired" in payload:
            asg["desired"] = max(int(asg.get("min") or 0), int(payload["desired"]))
        if "max" in payload:
            asg["max"] = int(payload["max"])
        _event(state, f"ASG {asg.get('name')} scaling policy fixed", "success")
        _save(session_id, entry)
        return {"ok": True, "message": "Scaling policy repaired", "asg": asg}

    ensure_v2(state)
    v2 = apply_v2_action(state, action, payload)
    if v2 is not None:
        if v2.get("ok"):
            _event(state, v2.get("message") or action, "success")
            _save(session_id, entry)
        return v2

    return {"ok": False, "error": f"Unknown action: {action}"}


# ── Grading ─────────────────────────────────────────────────────────────────
def _sg_by_name(state: dict, name: str) -> dict | None:
    return next((g for g in state.get("securityGroups", []) if g.get("name") == name or g.get("id") == name), None)


def _bucket(state: dict, name: str) -> dict | None:
    return next((b for b in state.get("s3Buckets", []) if b.get("name") == name), None)


def _v2_row(state: dict, service: str, resource: str, ident: str) -> dict | None:
    """Find one genericResources row by name or id (Lambda/RDS/DynamoDB/…)."""
    rows = ((state.get("genericResources") or {}).get(service) or {}).get(resource) or []
    return next((r for r in rows if r.get("name") == ident or r.get("id") == ident), None)


def validate_aws_lab(session_id: str, scenario_slug: str = "") -> tuple[bool, str]:
    """Grade per-scenario objectives from the broken-marker seeded at ensure time.

    Fail-closed: an unmapped slug with no broken markers does not auto-pass — it
    requires at least one learner action (a non-empty event log) so a freshly
    seeded world can't be graded as complete.
    """
    entry = _load(session_id)
    if not entry:
        return False, "No AWS session"
    state = entry["state"]
    _advance_lifecycle(state)
    _save(session_id, entry)
    broken = state.get("broken") or {}
    slug = (scenario_slug or entry.get("scenario_slug") or "").lower()

    # 1) Launch an instance with expected type + name, reached running.
    req = broken.get("require_launch")
    if req:
        want_type = req.get("type")
        want_name = req.get("name")
        # Accept free-tier cousins so Launch Wizard / CLI defaults cannot
        # silently fail grade when the objective asks for t3.micro.
        type_ok = None
        if want_type:
            cousins = {want_type}
            if want_type in ("t3.micro", "t2.micro"):
                cousins.update({"t3.micro", "t2.micro"})
            type_ok = cousins
        match = next(
            (
                i for i in state.get("instances", [])
                if i.get("state") == "running"
                and (type_ok is None or i.get("type") in type_ok)
                and (not want_name or i.get("name") == want_name or (i.get("tags") or {}).get("Name") == want_name)
            ),
            None,
        )
        if not match:
            return False, f"Launch a running {want_type or 'instance'} named {want_name or 'the target'}"
        return True, "Instance launched and running with the expected type and name"

    # 2) A named instance must be stopped.
    name = broken.get("require_stopped")
    if name:
        inst = _find_instance(state, name)
        if not inst:
            return False, f"Instance {name} not found"
        if inst.get("state") != "stopped":
            return False, f"Stop instance {name} (currently {inst.get('state')})"
        return True, f"Instance {name} is stopped"

    # 3) A named instance must be running (recovery).
    name = broken.get("require_running")
    if name:
        inst = _find_instance(state, name)
        if not inst:
            return False, f"Instance {name} not found"
        if inst.get("state") != "running":
            return False, f"Start instance {name} (currently {inst.get('state')})"
        return True, f"Instance {name} is running"

    # 4) SSH ingress restricted — no 0.0.0.0/0 on port 22 in the SG.
    sg_name = broken.get("restrict_ssh_sg")
    if sg_name:
        sg = _sg_by_name(state, sg_name)
        if not sg:
            return False, f"Security group {sg_name} not found"
        open_ssh = [
            r for r in sg.get("inbound", [])
            if int(r.get("from", 0)) <= 22 <= int(r.get("to", 0)) and r.get("source") in ("0.0.0.0/0", "::/0")
        ]
        if open_ssh:
            return False, f"SSH (port 22) is still open to 0.0.0.0/0 on {sg_name}"
        return True, f"SSH ingress on {sg_name} is restricted"

    # 5) Bucket must have default encryption enabled.
    bname = broken.get("require_bucket_encrypted")
    if bname:
        b = _bucket(state, bname)
        if not b:
            return False, f"Bucket {bname} not found"
        enc = str(b.get("encryption") or "").lower()
        if enc in ("", "none", "disabled"):
            return False, f"Enable default encryption on {bname}"
        return True, f"Bucket {bname} has default encryption enabled"

    # 6) Bucket must be private (public access blocked).
    bname = broken.get("require_bucket_private")
    if bname:
        b = _bucket(state, bname)
        if not b:
            return False, f"Bucket {bname} not found"
        if "not public" not in str(b.get("publicAccess") or "").lower():
            return False, f"Block public access on {bname}"
        return True, f"Bucket {bname} is not public"

    # 7) At least one non-terminated instance in the required (private) subnet.
    subnet_id = broken.get("require_instance_in_subnet")
    if subnet_id:
        match = next((i for i in state.get("instances", []) if i.get("subnetId") == subnet_id and i.get("state") != "terminated"), None)
        if not match:
            return False, f"Launch an instance in subnet {subnet_id}"
        return True, f"Workload present in subnet {subnet_id}"

    # 8) A required tag key=value on a named instance.
    tagreq = broken.get("require_tag")
    if tagreq:
        inst = _find_instance(state, tagreq.get("name"))
        if not inst:
            return False, f"Instance {tagreq.get('name')} not found"
        if (inst.get("tags") or {}).get(tagreq.get("key")) != tagreq.get("value"):
            return False, f"Add tag {tagreq.get('key')}={tagreq.get('value')} to {tagreq.get('name')}"
        return True, "Required tag present on the instance"

    # 9) A named CloudWatch alarm must exist.
    alarm_name = broken.get("require_cw_alarm")
    if alarm_name:
        if not any(a.get("name") == alarm_name for a in (state.get("cwAlarms") or [])):
            return False, f"Create the CloudWatch alarm {alarm_name}"
        return True, f"CloudWatch alarm {alarm_name} exists"

    # 10) A named Lambda function must exist and be Active.
    fn_name = broken.get("require_lambda")
    if fn_name:
        fn = _v2_row(state, "lambda", "functions", fn_name)
        if not fn:
            return False, f"Create the Lambda function {fn_name}"
        if str(fn.get("status") or "").lower() != "active":
            return False, f"Lambda function {fn_name} is {fn.get('status')}, not Active"
        return True, f"Lambda function {fn_name} is Active"

    # 11) A named RDS instance must exist and be available.
    db_name = broken.get("require_rds")
    if db_name:
        db = _v2_row(state, "rds", "databases", db_name)
        if not db:
            return False, f"Create the RDS database instance {db_name}"
        if str(db.get("status") or "").lower() != "available":
            return False, f"RDS instance {db_name} is {db.get('status')}, not available"
        return True, f"RDS instance {db_name} is available"

    # 12) A named DynamoDB table must exist.
    tbl_name = broken.get("require_dynamodb_table")
    if tbl_name:
        if not _v2_row(state, "dynamodb", "tables", tbl_name):
            return False, f"Create the DynamoDB table {tbl_name}"
        return True, f"DynamoDB table {tbl_name} exists"

    # 13) An ASG must be scaled to at least the required desired capacity.
    asg_req = broken.get("require_asg_desired")
    if asg_req:
        want_name = asg_req.get("name")
        want_min = int(asg_req.get("min") or 0)
        asg = next(
            (g for g in (state.get("autoScalingGroups") or [])
             if g.get("name") == want_name or g.get("id") == want_name),
            None,
        )
        if not asg:
            return False, f"Auto Scaling group {want_name} not found"
        desired = int(asg.get("desired") or 0)
        if desired < want_min:
            return False, f"Raise {want_name} desired capacity to at least {want_min} (currently {desired})"
        return True, f"Auto Scaling group {want_name} is at desired capacity {desired}"

    # 14) A Route 53 record of the required name+type must exist in some zone.
    r53 = broken.get("require_route53_record")
    if r53:
        want_name = r53.get("name")
        want_type = r53.get("type") or "A"
        zones = ((state.get("genericResources") or {}).get("route53") or {}).get("hosted-zones") or []
        found = any(
            rec.get("name") == want_name and rec.get("type") == want_type
            for z in zones for rec in (z.get("recordSets") or [])
        )
        if not found:
            return False, f"Create the {want_type} record {want_name} in a hosted zone"
        return True, f"Route 53 {want_type} record {want_name} exists"

    # 15) A named instance must carry the required IAM instance profile.
    role_req = broken.get("require_instance_role")
    if role_req:
        inst = _find_instance(state, role_req.get("name"))
        if not inst:
            return False, f"Instance {role_req.get('name')} not found"
        if inst.get("iamRole") != role_req.get("role"):
            return False, f"Attach role {role_req.get('role')} to {role_req.get('name')}"
        return True, f"Role {role_req.get('role')} attached to {role_req.get('name')}"

    # 16) Packer → AMI → EC2 → guest provenance chain (§X3 / §G2).
    from apps.vmware_sim.image_chain import slug_wants_image_chain, validate_image_chain
    chain_req = broken.get("require_image_chain")
    if chain_req is not None or slug_wants_image_chain(slug):
        req = chain_req if isinstance(chain_req, dict) else {}
        return validate_image_chain(state, session_id=session_id, require=req)

    # Custom validation_script objectives (JSON list of {check, ...}) if provided.
    vscript = state.get("validation_script")
    if vscript:
        ok, reason = _grade_script(state, vscript)
        return ok, reason

    # Fail-closed fallthrough: an unmapped AWS lab must not auto-pass on a
    # non-empty event log (that awarded XP for any console click). Explicit
    # broken markers or validation_script are required.
    return False, "NO_VALIDATION_SCRIPT"


def _grade_script(state: dict, vscript: Any) -> tuple[bool, str]:
    """Grade a scenario.validation_script consisting of a list of check dicts.

    Supported checks (all fail-closed): instance_running, instance_stopped,
    instance_type, instance_tag, sg_no_open_port, bucket_encrypted,
    bucket_private, instance_in_subnet.
    """
    checks = vscript
    if isinstance(vscript, str):
        try:
            checks = json.loads(vscript)
        except (ValueError, TypeError):
            return False, "Invalid validation_script"
    if isinstance(checks, dict):
        checks = checks.get("checks") or [checks]
    if not isinstance(checks, list):
        return False, "Invalid validation_script"
    for c in checks:
        if not isinstance(c, dict):
            continue
        kind = c.get("check")
        if kind == "instance_running":
            inst = _find_instance(state, c.get("instance"))
            if not inst or inst.get("state") != "running":
                return False, f"Instance {c.get('instance')} is not running"
        elif kind == "instance_stopped":
            inst = _find_instance(state, c.get("instance"))
            if not inst or inst.get("state") != "stopped":
                return False, f"Instance {c.get('instance')} is not stopped"
        elif kind == "instance_type":
            inst = _find_instance(state, c.get("instance"))
            if not inst or inst.get("type") != c.get("type"):
                return False, f"Instance {c.get('instance')} is not type {c.get('type')}"
        elif kind == "instance_tag":
            inst = _find_instance(state, c.get("instance"))
            if not inst or (inst.get("tags") or {}).get(c.get("key")) != c.get("value"):
                return False, f"Instance {c.get('instance')} missing tag {c.get('key')}={c.get('value')}"
        elif kind == "instance_in_subnet":
            match = next((i for i in state.get("instances", []) if i.get("subnetId") == c.get("subnet") and i.get("state") != "terminated"), None)
            if not match:
                return False, f"No instance in subnet {c.get('subnet')}"
        elif kind == "sg_no_open_port":
            sg = _sg_by_name(state, c.get("group"))
            port = int(c.get("port", 22))
            if not sg:
                return False, f"Security group {c.get('group')} not found"
            open_rules = [r for r in sg.get("inbound", []) if int(r.get("from", 0)) <= port <= int(r.get("to", 0)) and r.get("source") in ("0.0.0.0/0", "::/0")]
            if open_rules:
                return False, f"Port {port} still open to 0.0.0.0/0 on {c.get('group')}"
        elif kind == "bucket_encrypted":
            b = _bucket(state, c.get("bucket"))
            if not b or str(b.get("encryption") or "").lower() in ("", "none", "disabled"):
                return False, f"Bucket {c.get('bucket')} is not encrypted"
        elif kind == "bucket_private":
            b = _bucket(state, c.get("bucket"))
            if not b or "not public" not in str(b.get("publicAccess") or "").lower():
                return False, f"Bucket {c.get('bucket')} is still public"
        elif kind == "image_chain":
            from apps.vmware_sim.image_chain import validate_image_chain
            ok, reason = validate_image_chain(
                state,
                require={k: v for k, v in c.items() if k != "check"},
            )
            if not ok:
                return False, reason
    return True, "AWS lab objectives met"
