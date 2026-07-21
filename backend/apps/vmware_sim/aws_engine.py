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
    "t2.nano": {"family": "General purpose", "vcpu": 1, "memGiB": 0.5, "arch": "x86_64"},
    "t2.micro": {"family": "General purpose", "vcpu": 1, "memGiB": 1, "arch": "x86_64", "freeTier": True},
    "t2.small": {"family": "General purpose", "vcpu": 1, "memGiB": 2, "arch": "x86_64"},
    "t2.medium": {"family": "General purpose", "vcpu": 2, "memGiB": 4, "arch": "x86_64"},
    "t2.large": {"family": "General purpose", "vcpu": 2, "memGiB": 8, "arch": "x86_64"},
    "t3.micro": {"family": "General purpose", "vcpu": 2, "memGiB": 1, "arch": "x86_64", "freeTier": True},
    "t3.small": {"family": "General purpose", "vcpu": 2, "memGiB": 2, "arch": "x86_64"},
    "t3.medium": {"family": "General purpose", "vcpu": 2, "memGiB": 4, "arch": "x86_64"},
    "t3.large": {"family": "General purpose", "vcpu": 2, "memGiB": 8, "arch": "x86_64"},
    "m5.large": {"family": "General purpose", "vcpu": 2, "memGiB": 8, "arch": "x86_64"},
    "m5.xlarge": {"family": "General purpose", "vcpu": 4, "memGiB": 16, "arch": "x86_64"},
    "c5.large": {"family": "Compute optimized", "vcpu": 2, "memGiB": 4, "arch": "x86_64"},
    "c5.xlarge": {"family": "Compute optimized", "vcpu": 4, "memGiB": 8, "arch": "x86_64"},
    "r5.large": {"family": "Memory optimized", "vcpu": 2, "memGiB": 16, "arch": "x86_64"},
    "r5.xlarge": {"family": "Memory optimized", "vcpu": 4, "memGiB": 32, "arch": "x86_64"},
}


def get_instance_type(t: str) -> dict:
    return INSTANCE_TYPES.get(t) or INSTANCE_TYPES["t2.micro"]


AMI_CATALOG: dict[str, dict] = {
    "ami-0c02fb55956c7d316": {"os": "amazon-linux-2023", "platform": "Linux/UNIX", "arch": "x86_64", "user": "ec2-user"},
    "ami-0557a15b87f6559cf": {"os": "ubuntu-22.04", "platform": "Ubuntu", "arch": "x86_64", "user": "ubuntu"},
    "ami-0e001c9271cf7f3b9": {"os": "ubuntu-24.04", "platform": "Ubuntu", "arch": "x86_64", "user": "ubuntu"},
    "ami-026ebd4cfe2c043b2": {"os": "rhel-9", "platform": "Red Hat", "arch": "x86_64", "user": "ec2-user"},
}


def get_ami(ami_id: str) -> dict:
    return AMI_CATALOG.get(ami_id) or AMI_CATALOG["ami-0c02fb55956c7d316"]


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
            {"id": "rtb-0a1b2c3d4e5f67892", "region": "us-east-1", "vpcId": "vpc-0a1b2c3d4e5f67890", "main": True, "routes": [{"dest": "172.31.0.0/16", "target": "local"}, {"dest": "0.0.0.0/0", "target": "igw-0a1b2c3d4e5f67891"}]},
        ],
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
        "iamGroups": [
            {"id": new_iam_group_id(), "name": "Administrators", "created": "2024-01-05T09:00:00Z", "users": ["admin-user"], "policies": ["AdministratorAccess"]},
            {"id": new_iam_group_id(), "name": "Developers", "created": "2024-01-05T09:00:00Z", "users": ["developer-user"], "policies": ["PowerUserAccess"]},
            {"id": new_iam_group_id(), "name": "ReadOnly", "created": "2024-01-05T09:00:00Z", "users": ["readonly-user"], "policies": ["ReadOnlyAccess"]},
        ],
        "iamRoles": [
            {"id": new_iam_role_id(), "name": "EC2InstanceRole", "created": "2024-01-05T09:00:00Z", "trustedEntity": "ec2.amazonaws.com", "policies": ["AmazonS3ReadOnlyAccess", "CloudWatchAgentServerPolicy"]},
            {"id": new_iam_role_id(), "name": "LambdaExecutionRole", "created": "2024-01-05T09:00:00Z", "trustedEntity": "lambda.amazonaws.com", "policies": ["AWSLambdaBasicExecutionRole"]},
        ],
        "iamPolicies": [
            {"name": "MyS3BucketPolicy", "type": "Customer managed", "attached": 1, "created": "2024-01-20T09:00:00Z", "description": "Allows access to a specific S3 bucket", "document": {"Version": "2012-10-17", "Statement": [{"Effect": "Allow", "Action": ["s3:GetObject", "s3:PutObject"], "Resource": "arn:aws:s3:::my-web-assets-demo-123456/*"}]}},
            {"name": "MyEC2Policy", "type": "Customer managed", "attached": 0, "created": "2024-01-20T09:00:00Z", "description": "EC2 read + start/stop for tagged resources", "document": {"Version": "2012-10-17", "Statement": [{"Effect": "Allow", "Action": ["ec2:Describe*", "ec2:StartInstances", "ec2:StopInstances"], "Resource": "*"}]}},
        ],
        "cwAlarms": [
            {"name": "HighCPUUtilization", "region": "us-east-1", "metric": "CPUUtilization", "namespace": "AWS/EC2", "state": "OK", "threshold": "> 80% for 2/3 datapoints"},
        ],
        "goal": {"title": "AWS console lab", "objective": "Use the AWS console to fix the misconfigured resource."},
        "broken": {},
        "events": [],
        **seed_v2(),
    }


def _apply_preset(state: dict, slug: str) -> None:
    """Seed a scenario-specific broken world + objective from the slug heuristics."""
    slug = (slug or "").lower()
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
    elif "bucket" in slug and ("public" in slug or "block" in slug):
        state["goal"] = {"title": "Block public access", "objective": "Turn off public access on my-web-assets-demo-123456."}
        state["broken"] = {"require_bucket_private": "my-web-assets-demo-123456"}
    elif "private-subnet" in slug or "private_subnet" in slug:
        state["goal"] = {"title": "Move workload to private subnet", "objective": "Launch an instance in the private subnet (subnet-0a1b2c3d4e5f10003)."}
        state["broken"] = {"require_instance_in_subnet": "subnet-0a1b2c3d4e5f10003"}
    elif "tag" in slug:
        state["goal"] = {"title": "Tag the instance", "objective": "Add the tag Environment=production to db-server-01."}
        state["broken"] = {"require_tag": {"name": "db-server-01", "key": "Environment", "value": "production"}}


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
        count = int(payload.get("count") or 1)
        subnet_id = payload.get("subnet_id") or payload.get("subnetId") or ""
        subnets = state.get("subnets", [])
        subnet = next((s for s in subnets if s.get("id") == subnet_id), None) or next((s for s in subnets if s.get("region") == region), None)
        if subnet_id and subnet is None:
            return {"ok": False, "error": f"The subnet ID '{subnet_id}' does not exist"}
        sg_ids = payload.get("security_groups") or payload.get("securityGroups") or ["sg-0a1b2c3default03"]
        key_name = payload.get("key_name") or payload.get("keyName") or ""
        tags = payload.get("tags") or {}
        ami = get_ami(ami_id)
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
                "amiId": ami_id, "os": ami["os"], "type": itype, "az": az,
                "subnetId": (subnet or {}).get("id", ""), "vpcId": (subnet or {}).get("vpcId", ""),
                "publicIp": pub, "privateIp": priv, "keyName": key_name,
                "securityGroups": list(sg_ids), "iamRole": "", "monitoring": "enabled" if payload.get("monitoring") else "disabled",
                "rootDevice": "/dev/xvda", "rootVolume": rootvol, "launchTime": _now_iso(),
                "statusChecks": "initializing", "tenancy": "default", "architecture": get_instance_type(itype)["arch"],
                "tags": inst_tags,
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
        snap = {
            "id": payload.get("snapshot_id") or f"snap-{_hex(17)}",
            "region": region,
            "volumeId": vol_id,
            "size": (vol or {}).get("size") or int(payload.get("size") or 8),
            "state": "completed",
            "progress": "100%",
            "description": payload.get("description") or "",
            "started": _now_iso(),
            "encrypted": bool((vol or {}).get("encrypted")),
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

    if action == "create_image":
        inst_id = payload.get("instance_id") or ""
        inst = _find_instance(state, inst_id) if inst_id else None
        if not inst:
            return {"ok": False, "error": f"The instance ID '{inst_id}' does not exist"}
        ami = {
            "id": payload.get("ami_id") or new_ami_id(),
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
        }
        state.setdefault("amis", []).append(ami)
        _event(state, f"AMI {ami['id']} created from {inst_id}", "success")
        _save(session_id, entry)
        return {"ok": True, "message": "CreateImage succeeded", "ami_id": ami["id"]}

    if action == "deregister_image":
        ami_id = payload.get("ami_id") or payload.get("id")
        before = len(state.get("amis") or [])
        state["amis"] = [a for a in (state.get("amis") or []) if a.get("id") != ami_id]
        if len(state.get("amis") or []) == before:
            return {"ok": False, "error": f"The AMI ID '{ami_id}' does not exist"}
        _event(state, f"AMI {ami_id} deregistered", "info")
        _save(session_id, entry)
        return {"ok": True, "message": "DeregisterImage succeeded"}

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
        key = {
            "id": payload.get("access_key_id") or new_access_key_id(),
            "created": _now_iso(),
            "status": "Active",
            "lastUsed": "N/A",
        }
        user.setdefault("accessKeys", []).append(key)
        _event(state, f"Access key created for {uname}", "success")
        _save(session_id, entry)
        return {"ok": True, "message": "CreateAccessKey succeeded", "access_key_id": key["id"]}

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
        bucket["objects"] = [o for o in bucket.get("objects", []) if o.get("key") != key]
        bucket["objects"].append({"key": key, "size": int(payload.get("size") or 0), "modified": _now_iso(), "storageClass": "STANDARD"})
        _event(state, f"Uploaded {key} to {name}", "info")
        _save(session_id, entry)
        return {"ok": True, "message": "PutObject succeeded"}

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
        match = next(
            (
                i for i in state.get("instances", [])
                if i.get("state") == "running"
                and (not want_type or i.get("type") == want_type)
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

    # Custom validation_script objectives (JSON list of {check, ...}) if provided.
    vscript = state.get("validation_script")
    if vscript:
        ok, reason = _grade_script(state, vscript)
        return ok, reason

    # Fail-closed fallthrough: an unmapped AWS lab requires learner activity.
    if not state.get("events"):
        return False, "NO_VALIDATION_SCRIPT"
    return True, "AWS lab objectives met"


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
    return True, "AWS lab objectives met"
