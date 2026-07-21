"""In-memory Terraform + AWS CLI simulator for IaC training labs."""

from __future__ import annotations

import copy
import json
import time
from typing import Any

from django.core.cache import cache

from .terraform_v2_facades import apply_v2_action, ensure_v2

SESSION_TTL = 7200

DEFAULT_FILES = {
    "main.tf": """terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

resource "aws_instance" "web" {
  ami           = var.ami_id
  instance_type = var.instance_type

  tags = {
    Name = "web-server"
  }
}
""",
    "variables.tf": """variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "ap-south-1"
}

variable "ami_id" {
  description = "AMI for the web server"
  type        = string
  default     = "ami-0c55b159cbfafe1f0"
}

variable "instance_type" {
  description = "EC2 instance type"
  type        = string
  default     = "t3.medium"
}
""",
    "outputs.tf": """output "instance_id" {
  description = "ID of the web EC2 instance"
  value       = aws_instance.web.id
}

output "public_ip" {
  description = "Public IP of the web server"
  value       = aws_instance.web.public_ip
}
""",
}

# Broken VPC routing lab: private RT has no 0.0.0.0/0 → NAT Gateway.
VPC_ROUTING_BROKEN_FILES = {
    "main.tf": """terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}
""",
    "variables.tf": """variable "aws_region" {
  type    = string
  default = "us-east-1"
}
""",
    "network.tf": """resource "aws_vpc" "lab" {
  cidr_block = "10.40.0.0/16"
  tags       = { Name = "lab-vpc" }
}

resource "aws_subnet" "public" {
  vpc_id                  = aws_vpc.lab.id
  cidr_block              = "10.40.1.0/24"
  map_public_ip_on_launch = true
  availability_zone       = "us-east-1a"
  tags                    = { Name = "public" }
}

resource "aws_subnet" "private" {
  vpc_id                  = aws_vpc.lab.id
  cidr_block              = "10.40.2.0/24"
  map_public_ip_on_launch = false
  availability_zone       = "us-east-1a"
  tags                    = { Name = "private" }
}

resource "aws_internet_gateway" "gw" {
  vpc_id = aws_vpc.lab.id
}

resource "aws_eip" "nat" {
  domain = "vpc"
}

resource "aws_nat_gateway" "nat" {
  allocation_id = aws_eip.nat.id
  subnet_id     = aws_subnet.public.id
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.lab.id
}

resource "aws_route" "public_default" {
  route_table_id         = aws_route_table.public.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.gw.id
}

resource "aws_route_table_association" "public" {
  subnet_id      = aws_subnet.public.id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table" "private" {
  vpc_id = aws_vpc.lab.id
}

# BUG: private subnet has no default route to the NAT Gateway.
# Add something like:
# resource "aws_route" "private_default" {
#   route_table_id         = aws_route_table.private.id
#   destination_cidr_block = "0.0.0.0/0"
#   nat_gateway_id         = aws_nat_gateway.nat.id
# }

resource "aws_route_table_association" "private" {
  subnet_id      = aws_subnet.private.id
  route_table_id = aws_route_table.private.id
}
""",
    "outputs.tf": """output "private_subnet_id" {
  value = aws_subnet.private.id
}

output "nat_id" {
  value = aws_nat_gateway.nat.id
}
""",
}


def _session_key(session_id: str) -> str:
    return f"terraform_session:{session_id}"


def _load(session_id: str) -> dict | None:
    data = cache.get(_session_key(str(session_id)))
    if data is None:
        return None
    return json.loads(data) if isinstance(data, str) else data


def _save(session_id: str, entry: dict) -> None:
    cache.set(_session_key(str(session_id)), json.dumps(entry, default=str), SESSION_TTL)


def clear_session(session_id: str) -> None:
    """Remove Terraform/AWS CLI lab state when the parent lab session terminates."""
    cache.delete(_session_key(str(session_id)))


def _sync_files_to_sim_shell(session_id: str, files: dict) -> None:
    """Mirror Terraform IDE files into the simulation shell filesystem."""
    try:
        from apps.labs.provisioner.simulation.shell import get_sim_session

        entry = get_sim_session(str(session_id))
        if not entry:
            return
        engine = entry.get("state", {}).get("engine")
        if not engine or not getattr(engine, "shell", None):
            return
        st = engine.shell.state
        st._mkdir("/root/terraform")
        for name, content in files.items():
            if isinstance(name, str) and name.endswith(".tf") and isinstance(content, str):
                st._write_file(f"/root/terraform/{name}", content)
    except Exception:
        pass


def _iac_tool(slug: str = "") -> str:
    return "Terraform"


def _normalize_action(action: str) -> str:
    return action


def _format_init_output(tool: str) -> str:
    return (
        f"\nInitializing the backend...\n\n"
        f"Initializing provider plugins...\n"
        f"- Finding hashicorp/aws versions matching \"~> 5.0\"...\n"
        f"- Installing hashicorp/aws v5.82.0...\n"
        f"- Installed hashicorp/aws v5.82.0 (signed by HashiCorp)\n\n"
        f"{tool} has been successfully initialized!\n"
    )


def _format_plan_output(tool: str, files: dict, plan: dict, slug: str) -> str:
    main = files.get("main.tf", "")
    lines = [
        f"{tool} used the selected providers to generate the following execution plan.",
        "Resource actions are indicated with the following symbols:",
        "  + create",
        "  ~ update in-place",
        "",
    ]
    if "aws_instance" in main:
        lines.extend([
            "  # aws_instance.web will be created",
            '  + resource "aws_instance" "web" {',
            '      + ami           = "ami-0c55b159cbfafe1f0"',
            '      + instance_type = "t3.medium"',
            '      + tags          = { "Name" = "web-server" }',
            "    }",
            "",
        ])
    if "vsphere_virtual_machine" in main or "vmware" in slug:
        lines.extend([
            "  # vsphere_virtual_machine.clone will be created",
            '  + resource "vsphere_virtual_machine" "clone" {',
            '      + name     = "lab-clone-01"',
            "      + num_cpus = 2",
            "      + memory   = 4096",
            "    }",
            "",
        ])
    if plan.get("change", 0):
        lines.extend([
            "  # aws_security_group.web-sg will be updated in-place",
            '  ~ resource "aws_security_group" "web-sg" {',
            "      ~ ingress = (known after apply)",
            "    }",
            "",
        ])
    lines.append(plan.get("summary") or "Plan: 0 to add, 0 to change, 0 to destroy.")
    if "lock" in slug and plan.get("change", 0):
        lines.append("\nNote: state was locked — run force-unlock if planning fails.")
    return "\n".join(lines)


def _format_apply_output(tool: str, tf: dict) -> str:
    resources = tf.get("resources") or []
    lines = [
        f"{tool} apply — auto-approving plan",
        "",
        *(_format_plan_output(tool, {}, {"summary": "Plan applied.", "change": 0}, "").split("\n")[:4]),
        "",
    ]
    for r in resources:
        lines.append(f"{r.get('type')}.{r.get('name')}: Creating...")
        lines.append(f"{r.get('type')}.{r.get('name')}: Creation complete")
    lines.extend([
        "",
        "Apply complete! Resources: 3 added, 0 changed, 0 destroyed.",
        "",
        "Outputs:",
        "",
        "instance_id = \"i-0abc123def456\"",
        "public_ip   = \"203.0.113.42\"",
    ])
    return "\n".join(lines)


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _base_state() -> dict:
    return {
        "files": copy.deepcopy(DEFAULT_FILES),
        "active_file": "main.tf",
        "terraform": {
            "initialized": False,
            "workspace": "default",
            "last_plan": None,
            "last_apply": None,
            "resources": [],
            "drift_detected": True,
        },
        "aws": {
            "profile": "training",
            "region": "ap-south-1",
            "caller_identity": "arn:aws:iam::123456789012:user/training",
            "resources": [
                {"type": "aws_s3_bucket", "id": "app-logs-prod", "status": "ok"},
                {"type": "aws_instance", "id": "i-0abc123", "status": "running"},
            ],
        },
        "goal": {"title": "Fix IaC", "objective": "Edit Terraform files, then run init, plan, and apply in the terminal to reconcile drift."},
        "broken": {"drift": True, "plan_required": True},
        "events": [],
    }


def _hcl_has_private_nat_route(files: dict) -> bool:
    """True when HCL declares a 0.0.0.0/0 route via nat_gateway_id attribute (uncommented)."""
    import re
    joined = "\n".join(str(v) for v in (files or {}).values() if isinstance(v, str))
    lines = []
    for line in joined.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        lines.append(stripped)
    body = "\n".join(lines)
    has_nat_attr = bool(re.search(r"(?m)^\s*nat_gateway_id\s*=", body))
    has_default = '"0.0.0.0/0"' in body or "'0.0.0.0/0'" in body
    return has_nat_attr and has_default


def _apply_preset(state: dict, slug: str) -> None:
    slug = (slug or "").lower()
    tool = _iac_tool(slug)
    if "vpc-routing" in slug or "vpc_routing" in slug:
        state["files"] = copy.deepcopy(VPC_ROUTING_BROKEN_FILES)
        state["active_file"] = "network.tf"
        state["goal"] = {
            "title": "Fix private subnet internet access",
            "objective": (
                "The private route table is missing 0.0.0.0/0 → NAT Gateway. "
                "Add the aws_route, then terraform plan/apply (or add the route in the AWS Console)."
            ),
        }
        state["broken"] = {"missing_nat_route": True, "plan_required": True}
        state["terraform"]["initialized"] = False
        return
    if "lock" in slug:
        state["goal"] = {
            "title": "Unlock state",
            "objective": "Fix main.tf if needed, force-unlock the stale state lock, then re-run plan/apply in the terminal.",
        }
        state["broken"] = {"stale_lock": True, "plan_required": True}
        state["terraform"]["initialized"] = True
    elif "aws" in slug or "s3" in slug:
        state["goal"] = {
            "title": "AWS resource fix",
            "objective": "Update Terraform files and use aws cli to verify the S3 bucket policy.",
        }
    if "vmware" in slug:
        state["goal"]["objective"] = "Apply Terraform to clone a VM from template in VMware."
        state["files"]["main.tf"] = """terraform {
  required_providers {
    vsphere = {
      source  = "hashicorp/vsphere"
      version = "~> 2.0"
    }
  }
}

provider "vsphere" {
  user           = var.vcenter_user
  password       = var.vcenter_password
  vsphere_server = var.vcenter_host
}

resource "vsphere_virtual_machine" "clone" {
  name             = var.vm_name
  resource_pool_id = data.vsphere_resource_pool.pool.id
  datastore_id     = data.vsphere_datastore.datastore.id
  num_cpus         = 2
  memory           = 4096
  guest_id         = data.vsphere_virtual_machine.template.guest_id
  clone {
    template_uuid = data.vsphere_virtual_machine.template.id
  }
}
"""


def _ensure(session_id: str, slug: str = "") -> dict:
    entry = _load(session_id)
    if entry is None:
        state = _base_state()
        _apply_preset(state, slug)
        entry = {"session_id": str(session_id), "scenario_slug": slug, "state": state}
        _save(session_id, entry)
    elif "files" not in entry.get("state", {}):
        entry["state"]["files"] = copy.deepcopy(DEFAULT_FILES)
        entry["state"].setdefault("active_file", "main.tf")
        _save(session_id, entry)
    return entry


def get_state(session_id: str, scenario_slug: str = "") -> dict:
    entry = _ensure(session_id, scenario_slug)
    ensure_v2(entry["state"])
    _save(session_id, entry)
    slug = entry.get("scenario_slug") or scenario_slug
    return {
        "session_id": str(session_id),
        "scenario_slug": slug,
        "iac_tool": _iac_tool(slug).lower(),
        "state": copy.deepcopy(entry["state"]),
    }


def drop_session(session_id: str) -> None:
    cache.delete(_session_key(str(session_id)))


def apply_action(session_id: str, action: str, payload: dict | None = None) -> dict:
    payload = payload or {}
    entry = _load(session_id)
    if not entry:
        return {"ok": False, "error": "Terraform session not found"}
    state = entry["state"]
    tf = state["terraform"]
    broken = state.get("broken") or {}
    files = state.setdefault("files", copy.deepcopy(DEFAULT_FILES))
    slug = entry.get("scenario_slug") or ""
    tool = _iac_tool(slug)
    action = _normalize_action(action)

    if action == "delete_file":
        path = payload.get("path") or ""
        if path not in files:
            return {"ok": False, "error": "File not found"}
        if path in ("main.tf", "variables.tf", "outputs.tf"):
            return {"ok": False, "error": f"Cannot delete required file {path}"}
        del files[path]
        if state.get("active_file") == path:
            state["active_file"] = "main.tf"
        state["events"].insert(0, {"time": _now_iso(), "message": f"Deleted {path}", "severity": "info"})
        _save(session_id, entry)
        return {"ok": True, "message": f"Deleted {path}"}

    if action == "save_files":
        incoming = payload.get("files") or {}
        if not isinstance(incoming, dict):
            return {"ok": False, "error": "Invalid files payload"}
        for path, content in incoming.items():
            if isinstance(path, str) and path.endswith(".tf") and isinstance(content, str):
                files[path] = content
        if payload.get("active_file") in files:
            state["active_file"] = payload["active_file"]
        if broken.get("missing_nat_route") and _hcl_has_private_nat_route(files):
            broken["missing_nat_route"] = False
            state["broken"] = broken
        state["events"].insert(0, {"time": _now_iso(), "message": "Terraform files saved", "severity": "info"})
        _sync_files_to_sim_shell(session_id, files)
        _save(session_id, entry)
        return {"ok": True, "message": "Files saved"}

    if action == "set_active_file":
        path = payload.get("path") or ""
        if path in files:
            state["active_file"] = path
            _save(session_id, entry)
            return {"ok": True}
        return {"ok": False, "error": "File not found"}

    if action == "terraform_init":
        tf["initialized"] = True
        out = _format_init_output(tool)
        state["events"].insert(0, {"time": _now_iso(), "message": f"{tool} initialized", "severity": "info"})
        _save(session_id, entry)
        return {"ok": True, "output": out, "message": f"{tool} initialized"}

    if action == "terraform_validate":
        main = files.get("main.tf", "")
        if not main.strip():
            return {"ok": False, "output": "Error: main.tf is empty", "error": "Configuration invalid"}
        if "resource " not in main and "module " not in main:
            return {"ok": False, "output": "Error: No resources declared in main.tf", "error": "Configuration invalid"}
        out = "Success! The configuration is valid.\n"
        state["events"].insert(0, {"time": _now_iso(), "message": "Configuration validated", "severity": "info"})
        _save(session_id, entry)
        return {"ok": True, "output": out}

    if action == "terraform_plan":
        if not tf.get("initialized"):
            return {"ok": False, "error": f"Run {tool.lower()} init first"}
        if broken.get("stale_lock"):
            return {"ok": False, "error": "Error: state lock held — run force-unlock first", "output": "Error acquiring the state lock\n\nLock ID: fixitlab-lock\n"}
        has_instance = "aws_instance" in files.get("main.tf", "")
        has_vm = "vsphere_virtual_machine" in files.get("main.tf", "")
        plan = {
            "add": 1 if (has_instance or has_vm) else 0,
            "change": 2 if broken.get("drift") else 0,
            "destroy": 0,
            "summary": f"Plan: {1 if (has_instance or has_vm) else 0} to add, {2 if broken.get('drift') else 0} to change, 0 to destroy.",
        }
        tf["last_plan"] = plan
        broken["plan_required"] = False
        out = _format_plan_output(tool, files, plan, slug)
        state["events"].insert(0, {"time": _now_iso(), "message": plan["summary"], "severity": "info"})
        _save(session_id, entry)
        return {"ok": True, "plan": plan, "output": out}

    if action == "terraform_apply":
        if not tf.get("last_plan"):
            return {"ok": False, "error": f"Run {tool.lower()} plan first"}
        tf["last_apply"] = _now_iso()
        tf["drift_detected"] = False
        broken.pop("drift", None)
        broken.pop("stale_lock", None)
        main = files.get("main.tf", "")
        resources = []
        if "aws_instance" in main:
            resources.append({"type": "aws_instance", "name": "web", "status": "applied"})
            resources.append({"type": "aws_security_group", "name": "web-sg", "status": "applied"})
        if "vsphere_virtual_machine" in main:
            resources.append({"type": "vsphere_virtual_machine", "name": "clone", "status": "applied"})
        if not resources:
            resources = [{"type": "aws_instance", "name": "web", "status": "applied"}]
        tf["resources"] = resources
        out = _format_apply_output(tool, tf)
        state["events"].insert(
            0,
            {"time": _now_iso(), "message": "Apply complete! Resources provisioned.", "severity": "success"},
        )
        _save(session_id, entry)
        return {"ok": True, "message": "Apply complete", "output": out}

    if action == "force_unlock":
        broken.pop("stale_lock", None)
        state["events"].insert(0, {"time": _now_iso(), "message": "State lock force-unlocked", "severity": "success"})
        _save(session_id, entry)
        return {"ok": True, "message": "Lock released", "output": "Terraform state lock has been force-unlocked!"}

    if action == "aws_cli":
        cmd = (payload.get("command") or "").strip()
        from apps.labs.provisioner.simulation.simulation_modules import _handle_aws_cli_local

        low = cmd.lower()
        if low.startswith("aws sts get-caller-identity"):
            return {"ok": True, "output": _handle_aws_cli_local(cmd)}
        if any(x in low for x in (
            "s3 ls", "s3api", "ec2 describe", "iam list", "iam get-user",
            "eks list", "eks describe", "lambda list", "cloudwatch describe",
            "logs describe", "autoscaling describe",
        )):
            return {"ok": True, "output": _handle_aws_cli_local(cmd)}
        return {"ok": True, "output": _handle_aws_cli_local(cmd)}

    ensure_v2(state)
    v2 = apply_v2_action(state, action, payload)
    if v2 is not None:
        if v2.get("ok"):
            _save(session_id, entry)
        return v2

    return {"ok": False, "error": f"Unknown action: {action}"}


def validate_terraform_lab(session_id: str, scenario_slug: str = "") -> tuple[bool, str]:
    entry = _load(session_id)
    if not entry:
        return False, "No Terraform session"
    state = entry["state"]
    broken = state.get("broken") or {}
    tf = state.get("terraform") or {}
    slug = (scenario_slug or entry.get("scenario_slug") or "").lower()
    files = state.get("files") or {}

    if broken.get("stale_lock"):
        return False, "State lock still held — run terraform force-unlock"
    if broken.get("plan_required") and not tf.get("last_plan") and "vpc-routing" not in slug:
        return False, "Run terraform plan before apply"
    if broken.get("drift") or tf.get("drift_detected"):
        if not tf.get("last_apply"):
            return False, "Run terraform plan and apply to reconcile drift"
    if "lock" in slug and not tf.get("last_apply"):
        return False, "Unlock state and complete plan/apply"
    if "vpc-routing" in slug or broken.get("missing_nat_route"):
        if not _hcl_has_private_nat_route(files):
            return False, "Add a 0.0.0.0/0 route targeting the NAT Gateway on the private route table"
        if not tf.get("initialized"):
            return False, "Run terraform init first"
        if not tf.get("last_plan"):
            return False, "Run terraform plan"
        if not tf.get("last_apply"):
            return False, "Run terraform apply after adding the NAT route"
        broken["missing_nat_route"] = False
        state["broken"] = broken
        _save(session_id, entry)
        return True, "Private subnet routes 0.0.0.0/0 via NAT Gateway"
    if not tf.get("initialized"):
        return False, "Run terraform init first"
    if not tf.get("last_plan"):
        return False, "Run terraform plan"
    if not tf.get("last_apply"):
        return False, "Run terraform apply to provision resources"
    main_tf = files.get("main.tf", "")
    if "lock" in slug and "resource" not in main_tf and "aws_instance" not in main_tf:
        pass  # lock scenario may not require file edits
    return True, "Terraform lab objectives met"
