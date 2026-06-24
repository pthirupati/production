"""In-memory Terraform + AWS CLI simulator for IaC training labs."""

from __future__ import annotations

import copy
import json
import time
from typing import Any

from django.core.cache import cache

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


def _session_key(session_id: str) -> str:
    return f"terraform_session:{session_id}"


def _load(session_id: str) -> dict | None:
    data = cache.get(_session_key(str(session_id)))
    if data is None:
        return None
    return json.loads(data) if isinstance(data, str) else data


def _save(session_id: str, entry: dict) -> None:
    cache.set(_session_key(str(session_id)), json.dumps(entry, default=str), SESSION_TTL)


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


def _apply_preset(state: dict, slug: str) -> None:
    slug = (slug or "").lower()
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
    return {
        "session_id": str(session_id),
        "scenario_slug": entry.get("scenario_slug") or scenario_slug,
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

    if action == "save_files":
        incoming = payload.get("files") or {}
        if not isinstance(incoming, dict):
            return {"ok": False, "error": "Invalid files payload"}
        for path, content in incoming.items():
            if isinstance(path, str) and path.endswith(".tf") and isinstance(content, str):
                files[path] = content
        if payload.get("active_file") in files:
            state["active_file"] = payload["active_file"]
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
        state["events"].insert(0, {"time": _now_iso(), "message": "Terraform initialized", "severity": "info"})
        _save(session_id, entry)
        return {"ok": True, "output": "Terraform has been successfully initialized!"}

    if action == "terraform_plan":
        if not tf.get("initialized"):
            return {"ok": False, "error": "Run terraform init first"}
        has_instance = "aws_instance" in files.get("main.tf", "")
        plan = {
            "add": 1 if has_instance else 0,
            "change": 2 if broken.get("drift") else 0,
            "destroy": 0,
            "summary": f"Plan: {1 if has_instance else 0} to add, {2 if broken.get('drift') else 0} to change, 0 to destroy.",
        }
        tf["last_plan"] = plan
        broken["plan_required"] = False
        state["events"].insert(0, {"time": _now_iso(), "message": plan["summary"], "severity": "info"})
        _save(session_id, entry)
        return {"ok": True, "plan": plan, "output": plan["summary"]}

    if action == "terraform_apply":
        if not tf.get("last_plan"):
            return {"ok": False, "error": "Run terraform plan first"}
        tf["last_apply"] = _now_iso()
        tf["drift_detected"] = False
        broken.pop("drift", None)
        broken.pop("stale_lock", None)
        tf["resources"] = [
            {"type": "aws_instance", "name": "web", "status": "applied"},
            {"type": "aws_security_group", "name": "web-sg", "status": "applied"},
        ]
        state["events"].insert(
            0,
            {
                "time": _now_iso(),
                "message": "Apply complete! Resources: 3 added, 0 changed, 0 destroyed.",
                "severity": "success",
            },
        )
        _save(session_id, entry)
        return {"ok": True, "message": "Apply complete", "output": "Apply complete! Resources: 3 added, 0 changed, 0 destroyed."}

    if action == "force_unlock":
        broken.pop("stale_lock", None)
        state["events"].insert(0, {"time": _now_iso(), "message": "State lock force-unlocked", "severity": "success"})
        _save(session_id, entry)
        return {"ok": True, "message": "Lock released", "output": "Terraform state lock has been force-unlocked!"}

    if action == "aws_cli":
        cmd = (payload.get("command") or "").strip()
        low = cmd.lower()
        if low.startswith("aws sts get-caller-identity"):
            return {"ok": True, "output": json.dumps({"Account": "123456789012", "Arn": state["aws"]["caller_identity"]}, indent=2)}
        if "s3 ls" in low:
            buckets = "\n".join(
                f"2024-01-15 10:00:00 {r['id']}" for r in state["aws"]["resources"] if r.get("type") == "aws_s3_bucket"
            ) or "2024-01-15 10:00:00 app-logs-prod"
            return {"ok": True, "output": buckets}
        if "s3api get-bucket-policy" in low or "s3api get-bucket-acl" in low:
            return {"ok": True, "output": json.dumps({"Version": "2012-10-17", "Statement": []}, indent=2)}
        if "ec2 describe-instances" in low:
            return {"ok": True, "output": "i-0abc123  running  t3.medium  ap-south-1a"}
        if "ec2 describe-vpcs" in low:
            return {"ok": True, "output": "vpc-0abc123  10.0.0.0/16  available"}
        if "iam list-users" in low:
            return {"ok": True, "output": "training\nautomation"}
        if "iam get-user" in low:
            return {"ok": True, "output": json.dumps({"User": {"UserName": "training"}}, indent=2)}
        if "eks list-clusters" in low:
            return {"ok": True, "output": "fixitlab-training"}
        if "lambda list-functions" in low:
            return {"ok": True, "output": "fixitlab-handler"}
        return {"ok": True, "output": f"(simulated) {cmd}"}

    return {"ok": False, "error": f"Unknown action: {action}"}


def validate_terraform_lab(session_id: str, scenario_slug: str = "") -> tuple[bool, str]:
    entry = _load(session_id)
    if not entry:
        return False, "No Terraform session"
    state = entry["state"]
    broken = state.get("broken") or {}
    tf = state.get("terraform") or {}
    slug = (scenario_slug or entry.get("scenario_slug") or "").lower()

    if broken.get("stale_lock"):
        return False, "State lock still held — run terraform force-unlock"
    if broken.get("plan_required"):
        return False, "Run terraform plan before apply"
    if broken.get("drift") or tf.get("drift_detected"):
        if not tf.get("last_apply"):
            return False, "Run terraform plan and apply to reconcile drift"
    if "lock" in slug and not tf.get("last_apply"):
        return False, "Unlock state and complete plan/apply"
    if not tf.get("initialized"):
        return False, "Run terraform init first"
    if not tf.get("last_plan"):
        return False, "Run terraform plan"
    if not tf.get("last_apply"):
        return False, "Run terraform apply to provision resources"
    files = state.get("files") or {}
    main_tf = files.get("main.tf", "")
    if "lock" in slug and "resource" not in main_tf and "aws_instance" not in main_tf:
        pass  # lock scenario may not require file edits
    return True, "Terraform lab objectives met"
