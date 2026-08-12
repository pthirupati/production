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


def _fmt_hcl_value(value: Any) -> str:
    """Render a resolved value the way `terraform plan` prints it."""
    if _is_unknown(value):
        return "(known after apply)"
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        return "[" + ", ".join(_fmt_hcl_value(v) for v in value) + "]"
    if isinstance(value, dict):
        inner = ", ".join(f'"{k}" = {_fmt_hcl_value(v)}' for k, v in sorted(value.items()))
        return "{" + (f" {inner} " if inner else "") + "}"
    return f'"{value}"'


_PLAN_SYMBOL = {
    "create": "+", "update": "~", "destroy": "-", "replace": "-/+", "no-op": " ",
}


def _format_plan_output(tool: str, files: dict, plan: dict, slug: str) -> str:
    """Render a real execution plan from the computed diff.

    Every line here is derived from the parsed config and the state file — no
    resource is printed unless the learner actually declared it.
    """
    actions = [a for a in (plan.get("actions") or []) if a.get("action") != "no-op"]
    lines = [
        f"{tool} used the selected providers to generate the following execution plan.",
        "Resource actions are indicated with the following symbols:",
    ]
    kinds = {a["action"] for a in actions}
    if "create" in kinds:
        lines.append("  + create")
    if "update" in kinds:
        lines.append("  ~ update in-place")
    if "destroy" in kinds:
        lines.append("  - destroy")
    if "replace" in kinds:
        lines.append("-/+ destroy and then create replacement")
    lines.append("")

    if not actions:
        lines.append("No changes. Your infrastructure matches the configuration.")
        lines.append("")
        lines.append(plan.get("summary") or "Plan: 0 to add, 0 to change, 0 to destroy.")
        return "\n".join(lines)

    for act in actions:
        kind = act["action"]
        sym = _PLAN_SYMBOL.get(kind, " ")
        addr = act["address"]
        if kind == "replace":
            reason = act.get("replace_reason") or "attribute forces replacement"
            lines.append(f"  # {addr} must be replaced")
            lines.append(f"  # ({reason})")
            if act.get("create_before_destroy"):
                lines.append("  # (create before destroy)")
        elif kind == "create":
            lines.append(f"  # {addr} will be created")
        elif kind == "update":
            lines.append(f"  # {addr} will be updated in-place")
        else:
            lines.append(f"  # {addr} will be destroyed")
        lines.append(f'  {sym} resource "{act["type"]}" "{act["name"]}" {{')
        if kind in ("create", "replace"):
            attrs = act.get("after") or {}
            width = max((len(k) for k in attrs), default=0)
            for key in sorted(attrs):
                lines.append(f"      + {key.ljust(width)} = {_fmt_hcl_value(attrs[key])}")
            if "id" not in attrs:
                lines.append(f"      + {'id'.ljust(width)} = (known after apply)")
        elif kind == "update":
            changes = act.get("changes") or {}
            width = max((len(k) for k in changes), default=0)
            for key in sorted(changes):
                ch = changes[key]
                if ch["action"] == "add":
                    lines.append(f"      + {key.ljust(width)} = {_fmt_hcl_value(ch['after'])}")
                elif ch["action"] == "remove":
                    lines.append(f"      - {key.ljust(width)} = {_fmt_hcl_value(ch['before'])}")
                else:
                    lines.append(
                        f"      ~ {key.ljust(width)} = {_fmt_hcl_value(ch['before'])}"
                        f" -> {_fmt_hcl_value(ch['after'])}"
                    )
        lines.append("    }")
        lines.append("")

    lines.append(plan.get("summary") or "Plan: 0 to add, 0 to change, 0 to destroy.")
    if "lock" in slug and plan.get("change", 0):
        lines.append("\nNote: state was locked — run force-unlock if planning fails.")
    return "\n".join(lines)


def _format_apply_output(tool: str, tf: dict, plan: dict | None = None, outputs: dict | None = None) -> str:
    """Render apply progress from the plan that was actually executed.

    The old version always claimed "3 added" and printed two hardcoded outputs
    regardless of what the learner declared.
    """
    plan = plan or {}
    actions = [a for a in (plan.get("actions") or []) if a.get("action") != "no-op"]
    lines = [f"{tool} apply — auto-approving plan", ""]
    if not actions:
        lines.append("No changes. Your infrastructure matches the configuration.")
        lines.append("")
        lines.append("Apply complete! Resources: 0 added, 0 changed, 0 destroyed.")
    else:
        verbs = {
            "create": ("Creating...", "Creation complete"),
            "replace": ("Destroying... (forces replacement)", "Replacement complete"),
            "update": ("Modifying...", "Modifications complete"),
            "destroy": ("Destroying...", "Destruction complete"),
        }
        for act in actions:
            start, done = verbs.get(act["action"], ("Applying...", "Apply complete"))
            lines.append(f"{act['address']}: {start}")
            lines.append(f"{act['address']}: {done}")
        lines.extend([
            "",
            f"Apply complete! Resources: {plan.get('add', 0)} added, "
            f"{plan.get('change', 0)} changed, {plan.get('destroy', 0)} destroyed.",
        ])
    if outputs:
        lines.extend(["", "Outputs:", ""])
        width = max((len(k) for k in outputs), default=0)
        for key in sorted(outputs):
            lines.append(f"{key.ljust(width)} = {_fmt_hcl_value(outputs[key])}")
    return "\n".join(lines)


def compute_outputs(config: dict, state: dict) -> dict:
    """Resolve each `output` block's value against the applied state."""
    out: dict[str, Any] = {}
    for name, attrs in (config.get("outputs") or {}).items():
        if not isinstance(attrs, dict) or "value" not in attrs:
            continue
        out[name] = resolve_value(attrs["value"], config, state)
    return out


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
            "state_file": empty_state(),
            "outputs": {},
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
    """True when a real aws_route sends 0.0.0.0/0 to the NAT gateway.

    Uses the HCL parser rather than substring matching so the three attributes
    must live on the *same* aws_route block, and so the route table it targets
    must actually be the one associated with the private subnet. The old
    substring version passed as soon as the words appeared anywhere in the
    workspace — including in two unrelated resources, or a string literal.
    Fails CLOSED on unparseable HCL.
    """
    try:
        config = parse_hcl_files(files or {})
    except HCLParseError:
        return False
    resources = config["resources"]

    # Identify the route tables associated with a non-public subnet.
    private_subnets = {
        addr for addr, node in resources.items()
        if node["type"] == "aws_subnet"
        and node["attributes"].get("map_public_ip_on_launch") is not True
    }
    private_rts: set[str] = set()
    for node in resources.values():
        if node["type"] != "aws_route_table_association":
            continue
        subnet_ref = _iter_refs(node["attributes"].get("subnet_id"))
        rt_ref = _iter_refs(node["attributes"].get("route_table_id"))
        subnet_addrs = {".".join(r.split(".")[:2]) for r in subnet_ref}
        if subnet_addrs & private_subnets:
            private_rts.update(".".join(r.split(".")[:2]) for r in rt_ref)

    nat_gateways = {a for a, n in resources.items() if n["type"] == "aws_nat_gateway"}
    for node in resources.values():
        if node["type"] != "aws_route":
            continue
        attrs = node["attributes"]
        if attrs.get("destination_cidr_block") != "0.0.0.0/0":
            continue
        nat_targets = {
            ".".join(r.split(".")[:2]) for r in _iter_refs(attrs.get("nat_gateway_id"))
        }
        if "nat_gateway_id" not in attrs:
            continue
        # The target must be a NAT gateway declared in this config (or a raw id).
        raw_nat = attrs.get("nat_gateway_id")
        if nat_targets and not (nat_targets & nat_gateways):
            continue
        if not nat_targets and not isinstance(raw_nat, str):
            continue
        rt_targets = {
            ".".join(r.split(".")[:2]) for r in _iter_refs(attrs.get("route_table_id"))
        }
        # When we could determine the private route tables, the route must
        # point at one of them; otherwise accept any resolvable route table.
        if private_rts and not (rt_targets & private_rts):
            continue
        return True
    return False


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


# ── Real HCL parsing ─────────────────────────────────────────────────────────
# The old implementation was a single `resource "T" "N"` regex that captured no
# attributes, so it could not tell an `ami = var.x` from an `ami = data...id`,
# could not see nested blocks (lifecycle, filter, tags), and happily matched
# resource headers inside comments or heredocs. Everything downstream — the
# plan diff, drift detection, and lab grading — was therefore guessing. This is
# a proper tokenizer + recursive-descent block parser over the HCL subset the
# labs actually use.


class HCLParseError(ValueError):
    """Raised when HCL is syntactically unparseable.

    Callers must fail CLOSED on this: a config we cannot parse is not a config
    that passes. Returning an empty resource list here would silently mark
    every learner correct.
    """

    def __init__(self, message: str, line: int = 0):
        self.line = line
        super().__init__(f"line {line}: {message}" if line else message)


_HCL_PUNCT = {"{", "}", "[", "]", "=", ",", "(", ")", ".", ":", "?"}


def _hcl_tokenize(src: str) -> list[tuple[str, Any, int]]:
    """Tokenize HCL into (kind, value, line) triples.

    Kinds: ident, string, number, bool, null, punct, newline.
    Comments (#, //, /* */) and heredocs are handled here so no downstream
    stage has to re-guess whether a `resource` keyword is real code.
    """
    toks: list[tuple[str, Any, int]] = []
    i, line, n = 0, 1, len(src)
    while i < n:
        c = src[i]
        if c == "\n":
            toks.append(("newline", "\n", line))
            line += 1
            i += 1
            continue
        if c in " \t\r":
            i += 1
            continue
        if c == "#" or src.startswith("//", i):
            while i < n and src[i] != "\n":
                i += 1
            continue
        if src.startswith("/*", i):
            end = src.find("*/", i + 2)
            if end == -1:
                raise HCLParseError("unterminated block comment", line)
            line += src.count("\n", i, end)
            i = end + 2
            continue
        if src.startswith("<<", i):
            # Heredoc: <<EOT / <<-EOT ... EOT. Value kept as a plain string.
            j = i + 2
            if j < n and src[j] == "-":
                j += 1
            tag_start = j
            while j < n and (src[j].isalnum() or src[j] == "_"):
                j += 1
            tag = src[tag_start:j]
            if not tag:
                raise HCLParseError("malformed heredoc marker", line)
            nl = src.find("\n", j)
            if nl == -1:
                raise HCLParseError(f"unterminated heredoc {tag}", line)
            body_lines: list[str] = []
            k = nl + 1
            closed = False
            while k <= n:
                eol = src.find("\n", k)
                if eol == -1:
                    eol = n
                raw = src[k:eol]
                if raw.strip() == tag:
                    closed = True
                    line += src.count("\n", i, eol)
                    i = eol
                    break
                body_lines.append(raw)
                k = eol + 1
            if not closed:
                raise HCLParseError(f"unterminated heredoc {tag}", line)
            toks.append(("string", "\n".join(body_lines), line))
            continue
        if c == '"':
            buf: list[str] = []
            j = i + 1
            while j < n:
                ch = src[j]
                if ch == "\\" and j + 1 < n:
                    nxt = src[j + 1]
                    buf.append({"n": "\n", "t": "\t", '"': '"', "\\": "\\"}.get(nxt, "\\" + nxt))
                    j += 2
                    continue
                if ch == '"':
                    break
                if ch == "\n":
                    raise HCLParseError("unterminated string", line)
                buf.append(ch)
                j += 1
            if j >= n:
                raise HCLParseError("unterminated string", line)
            toks.append(("string", "".join(buf), line))
            i = j + 1
            continue
        if c.isdigit() or (c == "-" and i + 1 < n and src[i + 1].isdigit()):
            j = i + 1
            while j < n and (src[j].isdigit() or src[j] == "."):
                j += 1
            raw = src[i:j]
            toks.append(("number", float(raw) if "." in raw else int(raw), line))
            i = j
            continue
        if c.isalpha() or c == "_":
            j = i
            while j < n and (src[j].isalnum() or src[j] in "_-"):
                j += 1
            word = src[i:j]
            if word in ("true", "false"):
                toks.append(("bool", word == "true", line))
            elif word == "null":
                toks.append(("null", None, line))
            else:
                toks.append(("ident", word, line))
            i = j
            continue
        if c in _HCL_PUNCT:
            toks.append(("punct", c, line))
            i += 1
            continue
        # Operators we do not model (arithmetic, comparison) still need to be
        # consumed so an expression like `count > 0` does not abort the parse.
        toks.append(("punct", c, line))
        i += 1
    toks.append(("eof", None, line))
    return toks


class _HCLParser:
    def __init__(self, toks: list[tuple[str, Any, int]]):
        self.toks = toks
        self.pos = 0

    def peek(self, offset: int = 0) -> tuple[str, Any, int]:
        idx = self.pos + offset
        return self.toks[idx] if idx < len(self.toks) else ("eof", None, 0)

    def next(self) -> tuple[str, Any, int]:
        tok = self.peek()
        self.pos += 1
        return tok

    def skip_newlines(self) -> None:
        while self.peek()[0] == "newline":
            self.pos += 1

    def at(self, kind: str, value: Any = None) -> bool:
        k, v, _ = self.peek()
        return k == kind and (value is None or v == value)

    def parse_body(self, top_level: bool) -> dict[str, Any]:
        """Parse a `{ ... }` body into {"attributes": {...}, "blocks": [...]}."""
        attributes: dict[str, Any] = {}
        blocks: list[dict[str, Any]] = []
        while True:
            self.skip_newlines()
            kind, value, line = self.peek()
            if kind == "eof":
                if top_level:
                    break
                raise HCLParseError("unexpected end of file inside block", line)
            if kind == "punct" and value == "}":
                if top_level:
                    raise HCLParseError("unbalanced '}'", line)
                self.next()
                break
            if kind not in ("ident", "string"):
                # Stray punctuation between statements — skip rather than abort
                # so a trailing comma in a body does not fail the whole file.
                self.next()
                continue
            # Distinguish `name = expr` from `name "label" { ... }` / `name { ... }`.
            label_off = 1
            labels: list[str] = []
            while self.peek(label_off)[0] == "string":
                labels.append(self.peek(label_off)[1])
                label_off += 1
            nxt_kind, nxt_val, nxt_line = self.peek(label_off)
            if nxt_kind == "punct" and nxt_val == "{":
                self.pos += label_off + 1
                body = self.parse_body(top_level=False)
                blocks.append({
                    "type": value,
                    "labels": labels,
                    "line": line,
                    "attributes": body["attributes"],
                    "blocks": body["blocks"],
                })
                continue
            if self.peek(1)[0] == "punct" and self.peek(1)[1] == "=":
                self.pos += 2
                attributes[value] = self.parse_expression()
                continue
            # Unknown construct (e.g. a bare identifier) — consume the line.
            while self.peek()[0] not in ("newline", "eof"):
                self.next()
        return {"attributes": attributes, "blocks": blocks}

    def parse_expression(self) -> Any:
        """Parse a value.

        Literals become Python values. Anything referential or computed becomes
        a {"__ref__": "aws_vpc.lab.id"} / {"__expr__": "..."} marker so the diff
        engine can tell "known after apply" from a real literal change.
        """
        self.skip_newlines()
        kind, value, line = self.peek()
        if kind == "punct" and value == "{":
            self.next()
            body = self.parse_body(top_level=False)
            obj = dict(body["attributes"])
            for blk in body["blocks"]:
                obj[blk["type"]] = {"__block__": blk}
            return obj
        if kind == "punct" and value == "[":
            self.next()
            items: list[Any] = []
            while True:
                self.skip_newlines()
                k, v, ln = self.peek()
                if k == "eof":
                    raise HCLParseError("unterminated list", ln)
                if k == "punct" and v == "]":
                    self.next()
                    break
                if k == "punct" and v == ",":
                    self.next()
                    continue
                items.append(self.parse_expression())
            return items
        if kind in ("string", "number", "bool", "null"):
            self.next()
            if kind == "string" and "${" in str(value):
                return {"__expr__": value}
            return value
        if kind == "ident":
            # Reference or function call: consume the dotted/indexed chain.
            parts: list[str] = []
            while True:
                k, v, _ = self.peek()
                if k in ("ident", "number"):
                    parts.append(str(v))
                    self.next()
                elif k == "punct" and v == ".":
                    parts.append(".")
                    self.next()
                elif k == "punct" and v == "[":
                    depth = 0
                    while True:
                        k2, v2, ln2 = self.peek()
                        if k2 == "eof":
                            raise HCLParseError("unterminated index", ln2)
                        if k2 == "punct" and v2 == "[":
                            depth += 1
                        elif k2 == "punct" and v2 == "]":
                            depth -= 1
                            self.next()
                            if depth == 0:
                                break
                            continue
                        self.next()
                elif k == "punct" and v == "(":
                    depth = 0
                    while True:
                        k2, v2, ln2 = self.peek()
                        if k2 == "eof":
                            raise HCLParseError("unterminated call", ln2)
                        if k2 == "punct" and v2 == "(":
                            depth += 1
                        elif k2 == "punct" and v2 == ")":
                            depth -= 1
                            self.next()
                            if depth == 0:
                                break
                            continue
                        self.next()
                    parts.append("()")
                else:
                    break
            ref = "".join(parts)
            return {"__ref__": ref} if ref else None
        self.next()
        return {"__expr__": str(value)}


def parse_hcl(src: str) -> dict[str, Any]:
    """Parse HCL text into {"attributes", "blocks"}. Raises HCLParseError."""
    return _HCLParser(_hcl_tokenize(src or "")).parse_body(top_level=True)


def parse_hcl_files(files: dict) -> dict[str, Any]:
    """Parse every .tf file in a workspace into one merged configuration.

    Returns {"resources": {...}, "data": {...}, "variables": {...},
             "outputs": {...}, "locals": {...}, "providers": [...]}.
    Raises HCLParseError naming the offending file.
    """
    config: dict[str, Any] = {
        "resources": {},
        "data": {},
        "variables": {},
        "outputs": {},
        "locals": {},
        "providers": [],
    }
    for fname in sorted((files or {}).keys()):
        content = (files or {}).get(fname)
        if not isinstance(fname, str) or not fname.endswith(".tf") or not isinstance(content, str):
            continue
        try:
            body = parse_hcl(content)
        except HCLParseError as exc:
            raise HCLParseError(f"{fname}: {exc}") from exc
        for blk in body["blocks"]:
            btype, labels = blk["type"], blk["labels"]
            if btype == "resource" and len(labels) >= 2:
                config["resources"][f"{labels[0]}.{labels[1]}"] = {
                    "mode": "managed",
                    "type": labels[0],
                    "name": labels[1],
                    "file": fname,
                    "line": blk["line"],
                    "attributes": blk["attributes"],
                    "blocks": blk["blocks"],
                }
            elif btype == "data" and len(labels) >= 2:
                config["data"][f"data.{labels[0]}.{labels[1]}"] = {
                    "mode": "data",
                    "type": labels[0],
                    "name": labels[1],
                    "file": fname,
                    "line": blk["line"],
                    "attributes": blk["attributes"],
                    "blocks": blk["blocks"],
                }
            elif btype == "variable" and labels:
                config["variables"][labels[0]] = blk["attributes"]
            elif btype == "output" and labels:
                config["outputs"][labels[0]] = blk["attributes"]
            elif btype == "locals":
                config["locals"].update(blk["attributes"])
            elif btype == "provider" and labels:
                config["providers"].append({"name": labels[0], "attributes": blk["attributes"]})
    return config


def _iter_refs(value: Any) -> list[str]:
    """Collect every `__ref__` string nested anywhere inside a parsed value."""
    found: list[str] = []
    if isinstance(value, dict):
        if "__ref__" in value and isinstance(value["__ref__"], str):
            found.append(value["__ref__"])
        for key, sub in value.items():
            if key == "__ref__":
                continue
            found.extend(_iter_refs(sub))
    elif isinstance(value, list):
        for sub in value:
            found.extend(_iter_refs(sub))
    return found


def _node_refs(node: dict) -> list[str]:
    refs = _iter_refs(node.get("attributes") or {})
    for blk in node.get("blocks") or []:
        refs.extend(_iter_refs(blk.get("attributes") or {}))
        refs.extend(_node_refs(blk))
    return refs


def build_dependency_graph(config: dict) -> dict[str, Any]:
    """Build the resource dependency graph Terraform uses to order operations.

    Returns {"nodes": [...], "edges": {node: [deps]}, "order": [...],
             "cycles": [[...]]}. `order` is the apply order (dependencies
    first); destroy order is its reverse.
    """
    nodes: dict[str, dict] = {}
    nodes.update(config.get("resources") or {})
    nodes.update(config.get("data") or {})

    def resolve(ref: str) -> str | None:
        parts = [p for p in ref.split(".") if p and p != "()"]
        if not parts:
            return None
        if parts[0] == "data" and len(parts) >= 3:
            key = f"data.{parts[1]}.{parts[2]}"
            return key if key in nodes else None
        if len(parts) >= 2:
            key = f"{parts[0]}.{parts[1]}"
            return key if key in nodes else None
        return None

    edges: dict[str, list[str]] = {}
    for key, node in nodes.items():
        deps: list[str] = []
        for ref in _node_refs(node):
            target = resolve(ref)
            if target and target != key and target not in deps:
                deps.append(target)
        explicit = node.get("attributes", {}).get("depends_on")
        for ref in _iter_refs(explicit) if explicit is not None else []:
            target = resolve(ref)
            if target and target != key and target not in deps:
                deps.append(target)
        edges[key] = deps

    # Kahn's algorithm; leftover nodes are in cycles.
    indeg = {k: 0 for k in nodes}
    for key, deps in edges.items():
        for _ in deps:
            indeg[key] += 1
    ready = sorted([k for k, d in indeg.items() if d == 0])
    order: list[str] = []
    remaining = dict(indeg)
    while ready:
        cur = ready.pop(0)
        order.append(cur)
        del remaining[cur]
        for key, deps in edges.items():
            if key in remaining and cur in deps:
                remaining[key] -= 1
                if remaining[key] == 0:
                    ready.append(key)
                    ready.sort()
    cycles = sorted(remaining.keys())
    return {
        "nodes": sorted(nodes.keys()),
        "edges": edges,
        "order": order,
        "cycles": [cycles] if cycles else [],
    }


# ── Value resolution, state file, and diffs ──────────────────────────────────

# Provider ForceNew metadata: changing one of these attributes destroys and
# recreates the resource rather than updating in place. This is what turns an
# AMI bump into "-/+ must be replaced" instead of a harmless in-place update.
FORCE_NEW_ATTRIBUTES: dict[str, set[str]] = {
    "aws_instance": {"ami", "availability_zone", "subnet_id", "user_data"},
    "aws_subnet": {"cidr_block", "vpc_id", "availability_zone"},
    "aws_vpc": {"cidr_block"},
    "aws_nat_gateway": {"subnet_id", "allocation_id"},
    "aws_route_table": {"vpc_id"},
    "aws_route": {"route_table_id", "destination_cidr_block"},
    "aws_eip": {"domain"},
    "aws_db_instance": {"engine", "availability_zone"},
    "aws_launch_template": set(),
    "vsphere_virtual_machine": {"datastore_id", "resource_pool_id"},
    "google_compute_instance": {"zone", "machine_type"},
    "azurerm_linux_virtual_machine": {"location", "size"},
}

# Attributes the provider computes at create time. A plan shows these as
# "(known after apply)" and a diff must never treat them as a change.
COMPUTED_ATTRIBUTES = {
    "id", "arn", "public_ip", "private_ip", "public_dns", "private_dns",
    "instance_state", "primary_network_interface_id", "allocation_id",
    "association_id", "owner_id", "unique_id", "self_link", "fqdn",
}


def resolve_value(value: Any, config: dict, state: dict | None = None, depth: int = 0) -> Any:
    """Resolve a parsed HCL value against variables, locals, and prior state.

    Unresolvable references (a computed attribute of a not-yet-created
    resource) come back as {"__unknown__": ref} — Terraform's "known after
    apply". This is what lets the diff distinguish a real change from a value
    that simply cannot be known at plan time.
    """
    if depth > 12:
        return {"__unknown__": "recursion"}
    if isinstance(value, list):
        return [resolve_value(v, config, state, depth + 1) for v in value]
    if isinstance(value, dict):
        if "__ref__" in value:
            return _resolve_ref(str(value["__ref__"]), config, state, depth)
        if "__expr__" in value:
            return {"__unknown__": str(value["__expr__"])}
        if "__block__" in value:
            blk = value["__block__"]
            return resolve_value(blk.get("attributes") or {}, config, state, depth + 1)
        return {k: resolve_value(v, config, state, depth + 1) for k, v in value.items()}
    return value


def _resolve_ref(ref: str, config: dict, state: dict | None, depth: int) -> Any:
    parts = [p for p in ref.split(".") if p and p != "()"]
    if not parts:
        return {"__unknown__": ref}
    head = parts[0]
    if head == "var" and len(parts) >= 2:
        var = (config.get("variables") or {}).get(parts[1])
        if isinstance(var, dict) and "default" in var:
            return resolve_value(var["default"], config, state, depth + 1)
        return {"__unknown__": ref}
    if head == "local" and len(parts) >= 2:
        locals_ = config.get("locals") or {}
        if parts[1] in locals_:
            return resolve_value(locals_[parts[1]], config, state, depth + 1)
        return {"__unknown__": ref}
    # data.<type>.<name>.<attr> and <type>.<name>.<attr> read from prior state.
    if head == "data" and len(parts) >= 3:
        key, attr = f"data.{parts[1]}.{parts[2]}", parts[3] if len(parts) > 3 else "id"
    elif len(parts) >= 2:
        key, attr = f"{parts[0]}.{parts[1]}", parts[2] if len(parts) > 2 else "id"
    else:
        return {"__unknown__": ref}
    resources = ((state or {}).get("resources") or {})
    if key in resources:
        attrs = resources[key].get("attributes") or {}
        if attr in attrs:
            return attrs[attr]
    return {"__unknown__": ref}


def resolve_resource_attributes(node: dict, config: dict, state: dict | None = None) -> dict:
    """Flatten a parsed resource into its resolved attribute map."""
    out = {k: resolve_value(v, config, state) for k, v in (node.get("attributes") or {}).items()}
    for blk in node.get("blocks") or []:
        btype = blk.get("type")
        if not btype or btype == "lifecycle":
            continue
        resolved = {k: resolve_value(v, config, state) for k, v in (blk.get("attributes") or {}).items()}
        prior = out.get(btype)
        if isinstance(prior, list):
            prior.append(resolved)
        elif isinstance(prior, dict):
            out[btype] = [prior, resolved]
        else:
            out[btype] = resolved
    return out


def lifecycle_of(node: dict) -> dict:
    """Extract the `lifecycle` meta-block flags for a parsed resource."""
    for blk in node.get("blocks") or []:
        if blk.get("type") == "lifecycle":
            attrs = blk.get("attributes") or {}
            ignore = attrs.get("ignore_changes")
            ignored: list[str] = []
            for item in ignore if isinstance(ignore, list) else ([ignore] if ignore else []):
                if isinstance(item, dict) and "__ref__" in item:
                    ignored.append(str(item["__ref__"]))
                elif isinstance(item, str):
                    ignored.append(item)
            return {
                "create_before_destroy": bool(attrs.get("create_before_destroy") is True),
                "prevent_destroy": bool(attrs.get("prevent_destroy") is True),
                "ignore_changes": ignored,
            }
    return {"create_before_destroy": False, "prevent_destroy": False, "ignore_changes": []}


def _is_unknown(value: Any) -> bool:
    return isinstance(value, dict) and "__unknown__" in value


def empty_state() -> dict:
    """A fresh terraform.tfstate skeleton."""
    return {"version": 4, "terraform_version": "1.7.5", "serial": 0, "lineage": "fixitlab", "resources": {}}


def diff_attributes(prior: dict, desired: dict, ignore: list[str] | None = None) -> dict[str, dict]:
    """Per-attribute +/-/~ diff between state and config.

    Computed and unknown values never register as changes — that is the bug
    that made every plan claim "2 to change" regardless of the config.
    """
    ignore_set = set(ignore or [])
    changes: dict[str, dict] = {}
    for key in sorted(set(prior) | set(desired)):
        if key in ignore_set or key in COMPUTED_ATTRIBUTES:
            continue
        before, after = prior.get(key), desired.get(key)
        if key not in desired:
            changes[key] = {"action": "remove", "before": before, "after": None}
        elif key not in prior:
            if _is_unknown(after):
                continue
            changes[key] = {"action": "add", "before": None, "after": after}
        elif _is_unknown(after) or _is_unknown(before):
            continue
        elif before != after:
            changes[key] = {"action": "update", "before": before, "after": after}
    return changes


def default_ami_registry() -> list[dict]:
    """The account's AMI catalog, newest first.

    Backs `data.aws_ami` lookups so an image can be deregistered out of band
    and the next plan legitimately selects a different id — real drift, not a
    preset boolean.
    """
    return [
        {"id": "ami-0a1b2c3d4e5f60011", "name": "app-golden-2026-08-01", "owner": "self",
         "creation_date": "2026-08-01T00:00:00Z", "state": "available", "architecture": "x86_64"},
        {"id": "ami-0a1b2c3d4e5f60010", "name": "app-golden-2026-07-15", "owner": "self",
         "creation_date": "2026-07-15T00:00:00Z", "state": "available", "architecture": "x86_64"},
        {"id": "ami-0c55b159cbfafe1f0", "name": "amzn2-ami-hvm-2026", "owner": "amazon",
         "creation_date": "2026-06-01T00:00:00Z", "state": "available", "architecture": "x86_64"},
    ]


def _ami_matches(image: dict, node: dict, config: dict, state: dict) -> bool:
    """Apply a data.aws_ami block's owners + filter blocks to one image."""
    attrs = node.get("attributes") or {}
    owners = resolve_value(attrs.get("owners"), config, state)
    if isinstance(owners, list) and owners:
        allowed = {str(o) for o in owners if not _is_unknown(o)}
        if allowed and str(image.get("owner")) not in allowed:
            return False
    for blk in node.get("blocks") or []:
        if blk.get("type") != "filter":
            continue
        battrs = blk.get("attributes") or {}
        fname = resolve_value(battrs.get("name"), config, state)
        values = resolve_value(battrs.get("values"), config, state)
        if _is_unknown(fname) or not isinstance(values, list):
            continue
        field = {"name": "name", "image-id": "id", "architecture": "architecture",
                 "state": "state"}.get(str(fname), str(fname))
        actual = str(image.get(field, ""))
        import fnmatch

        if not any(fnmatch.fnmatch(actual, str(v)) for v in values if not _is_unknown(v)):
            return False
    return True


def resolve_data_source(node: dict, config: dict, state: dict) -> dict:
    """Evaluate one data block into its attribute map."""
    dtype = node.get("type")
    attrs = resolve_resource_attributes(node, config, state)
    if dtype == "aws_ami":
        registry = [
            img for img in ((state or {}).get("ami_registry") or default_ami_registry())
            if img.get("state") == "available"
        ]
        matches = [img for img in registry if _ami_matches(img, node, config, state)]
        if not matches:
            # Fail CLOSED: real Terraform errors when a data.aws_ami matches
            # nothing. Silently inventing an id would hide the very drift these
            # labs are teaching.
            return {
                "__error__": "Your query returned no results. "
                "Please change your search criteria and try again.",
                "id": {"__unknown__": "data.aws_ami"},
            }
        most_recent = resolve_value((node.get("attributes") or {}).get("most_recent"), config, state)
        if most_recent is True:
            matches.sort(key=lambda i: str(i.get("creation_date")), reverse=True)
        chosen = matches[0]
        attrs.update({
            "id": chosen["id"], "image_id": chosen["id"], "name": chosen.get("name"),
            "owner_id": chosen.get("owner"), "creation_date": chosen.get("creation_date"),
            "architecture": chosen.get("architecture"),
        })
    return attrs


def refresh_data_sources(config: dict, state: dict, graph: dict | None = None) -> dict:
    """Re-evaluate every data block against current state; returns a new state."""
    data_nodes = config.get("data") or {}
    if not data_nodes:
        return state
    new_state = copy.deepcopy(state)
    resources = new_state.setdefault("resources", {})
    for key, node in data_nodes.items():
        attrs = resolve_data_source(node, config, new_state)
        resources[key] = {
            "mode": "data", "type": node["type"], "name": node["name"], "attributes": attrs,
        }
    return new_state


def data_source_errors(config: dict, state: dict) -> list[str]:
    """Human-readable errors from data sources that resolved to nothing."""
    refreshed = refresh_data_sources(config, state or empty_state())
    out: list[str] = []
    for key, entry in ((refreshed or {}).get("resources") or {}).items():
        err = (entry.get("attributes") or {}).get("__error__")
        if err:
            out.append(f"Error: reading {key}: {err}")
    return out


def compute_plan(config: dict, state: dict, graph: dict | None = None) -> dict:
    """Compare desired config against prior state and produce a real plan.

    Returns {"actions": [...], "add", "change", "destroy", "replace", "summary"}
    with one action per resource in dependency order.
    """
    graph = graph or build_dependency_graph(config)
    # Terraform reads data sources during plan, before any managed resource is
    # evaluated — so `ami = data.aws_ami.app.id` is a known value at plan time,
    # not "(known after apply)". Refresh them into a scratch state first.
    state = refresh_data_sources(config, state or empty_state(), graph)
    prior = (state or {}).get("resources") or {}
    desired = config.get("resources") or {}
    ordered = [k for k in graph["order"] if k in desired]
    ordered += [k for k in sorted(desired) if k not in ordered]

    actions: list[dict] = []
    for key in ordered:
        node = desired[key]
        life = lifecycle_of(node)
        attrs = resolve_resource_attributes(node, config, state)
        if key not in prior:
            actions.append({
                "address": key, "type": node["type"], "name": node["name"],
                "action": "create", "changes": {}, "after": attrs,
                "create_before_destroy": life["create_before_destroy"],
            })
            continue
        prior_attrs = (prior[key] or {}).get("attributes") or {}
        changes = diff_attributes(prior_attrs, attrs, life["ignore_changes"])
        if not changes:
            actions.append({
                "address": key, "type": node["type"], "name": node["name"],
                "action": "no-op", "changes": {}, "after": attrs,
                "create_before_destroy": life["create_before_destroy"],
            })
            continue
        forces_new = any(a in FORCE_NEW_ATTRIBUTES.get(node["type"], set()) for a in changes)
        actions.append({
            "address": key, "type": node["type"], "name": node["name"],
            "action": "replace" if forces_new else "update",
            "changes": changes, "after": attrs,
            "create_before_destroy": life["create_before_destroy"],
            "replace_reason": (
                f"{sorted(a for a in changes if a in FORCE_NEW_ATTRIBUTES.get(node['type'], set()))[0]} forces replacement"
                if forces_new else ""
            ),
        })

    for key in sorted(prior):
        if key in desired or str(key).startswith("data."):
            continue
        entry = prior[key] or {}
        actions.append({
            "address": key, "type": entry.get("type") or key.split(".")[0],
            "name": entry.get("name") or key.split(".")[-1],
            "action": "destroy", "changes": {}, "after": {},
            "create_before_destroy": False,
        })

    add = sum(1 for a in actions if a["action"] in ("create", "replace"))
    change = sum(1 for a in actions if a["action"] == "update")
    destroy = sum(1 for a in actions if a["action"] in ("destroy", "replace"))
    return {
        "actions": actions,
        "add": add,
        "change": change,
        "destroy": destroy,
        "replace": sum(1 for a in actions if a["action"] == "replace"),
        "summary": f"Plan: {add} to add, {change} to change, {destroy} to destroy.",
    }


def apply_plan_to_state(config: dict, state: dict, plan: dict) -> dict:
    """Commit a plan into the state file, bumping the serial.

    Attributes that were "(known after apply)" at plan time are re-resolved
    here against the state as it is being built, in dependency order — exactly
    when Terraform learns them. Writing the unknown marker through (or dropping
    the attribute) would make the very next plan report a spurious diff for
    every cross-resource reference.
    """
    new_state = refresh_data_sources(config, copy.deepcopy(state or empty_state()))
    resources = new_state.setdefault("resources", {})
    desired = config.get("resources") or {}

    for action in plan.get("actions") or []:
        addr, kind = action["address"], action["action"]
        if kind == "destroy":
            resources.pop(addr, None)
            continue
        node = desired.get(addr)
        prior_attrs = (resources.get(addr) or {}).get("attributes") or {}
        if kind == "no-op":
            continue
        # Pre-seed this resource's id so self-references and dependents resolve.
        rid = prior_attrs.get("id") or _synthetic_id(action["type"], action["name"])
        resources.setdefault(addr, {
            "mode": "managed", "type": action["type"], "name": action["name"],
            "attributes": {"id": rid},
        })
        attrs = (
            resolve_resource_attributes(node, config, new_state)
            if node is not None
            else dict(action.get("after") or {})
        )
        for name in COMPUTED_ATTRIBUTES:
            if name in prior_attrs and kind == "update":
                attrs.setdefault(name, prior_attrs[name])
        attrs["id"] = rid
        # Anything still unknown after apply is a genuinely computed value.
        attrs = {k: v for k, v in attrs.items() if not _is_unknown(v)}
        resources[addr] = {
            "mode": "managed", "type": action["type"], "name": action["name"],
            "attributes": attrs,
        }

    new_state["serial"] = int(new_state.get("serial") or 0) + 1
    new_state["updated_at"] = _now_iso()
    return new_state


def _synthetic_id(rtype: str, name: str) -> str:
    """Deterministic resource id so re-plans after apply are stable no-ops."""
    import hashlib

    digest = hashlib.blake2b(f"{rtype}.{name}".encode(), digest_size=6).hexdigest()
    if rtype == "aws_instance":
        return f"i-0{digest}"
    if rtype == "aws_vpc":
        return f"vpc-0{digest}"
    if rtype == "aws_subnet":
        return f"subnet-0{digest}"
    if rtype == "aws_nat_gateway":
        return f"nat-0{digest}"
    if rtype == "aws_route_table":
        return f"rtb-0{digest}"
    if rtype == "aws_internet_gateway":
        return f"igw-0{digest}"
    if rtype == "aws_eip":
        return f"eipalloc-0{digest}"
    if rtype == "aws_ami" or rtype.endswith("_ami"):
        return f"ami-0{digest}"
    return f"{rtype}-{digest}"


def _parse_tf_resources(hcl: str) -> list[dict[str, str]]:
    """Resource type/name pairs from HCL source.

    Kept as the stable shape the cloud-mirroring code consumes. Now backed by
    the real parser, with the old regex retained only as a salvage path so a
    syntactically broken file still mirrors what it can (apply/destroy of
    already-created cloud resources must not strand a learner's inventory).
    """
    import re

    out: list[dict[str, str]] = []
    seen: set[str] = set()
    try:
        config = parse_hcl_files({"main.tf": hcl or ""})
        for key, node in config["resources"].items():
            if key in seen:
                continue
            seen.add(key)
            entry = {"type": node["type"], "name": node["name"]}
            # Surface a few attributes the cloud mirror reads off the resource.
            for attr in ("tag", "cidr", "subnet", "space", "hostname", "image"):
                val = node["attributes"].get(attr)
                if isinstance(val, (str, int, float, bool)):
                    entry[attr] = val
            out.append(entry)
        return out
    except HCLParseError:
        pass
    for m in re.finditer(r'resource\s+"([^"]+)"\s+"([^"]+)"', hcl or ""):
        rtype, name = m.group(1), m.group(2)
        key = f"{rtype}.{name}"
        if key in seen:
            continue
        seen.add(key)
        out.append({"type": rtype, "name": name})
    return out


def _cloud_links_from_resources(resources: list[dict]) -> dict[str, bool]:
    types = {str(r.get("type") or "") for r in resources}
    return {
        "aws": any(t.startswith("aws_") for t in types),
        "azure": any(t.startswith("azurerm_") for t in types),
        "gcp": any(t.startswith("google_") for t in types),
        "vmware": any(t.startswith("vsphere_") for t in types),
        "maas": any(t.startswith("maas_") for t in types),
        "lxd": any(t.startswith("lxd_") for t in types),
    }


def _mirror_apply_to_clouds(session_id: str, resources: list[dict]) -> dict[str, bool]:
    """S1.5: terraform apply → AWS/Azure/GCP/VMware/MAAS/LXD inventory + identity.

    Idempotent: cloud engines return ok when the named VM/instance already exists.
    Failures are non-fatal so pure-AWS labs still complete apply.
    """
    links = _cloud_links_from_resources(resources)
    for r in resources:
        rtype = str(r.get("type") or "")
        name = str(r.get("name") or "web")
        try:
            if rtype == "aws_instance":
                from apps.vmware_sim import aws_engine as ae

                host = name if name != "web" else "web-server"
                aws_st = ae.get_state(session_id, "terraform-apply")
                existing = [
                    i for i in (aws_st.get("state") or {}).get("instances") or []
                    if (i.get("name") == host or (i.get("tags") or {}).get("Name") == host)
                    and (i.get("state") or "") != "terminated"
                ]
                if not existing:
                    ae.apply_action(
                        session_id,
                        "launch_instance",
                        {
                            "name": host,
                            "type": "t3.micro",
                            "count": 1,
                            "tags": {"Name": host, "ManagedBy": "terraform"},
                        },
                    )
                try:
                    from apps.labs.provisioner.simulation.server_identity import upsert_server

                    upsert_server(
                        session_id,
                        {
                            "id": f"tf-aws-{name}",
                            "hostname": host,
                            "primary_ip": "10.0.1.10",
                            "power": "on",
                            "os": "amazon-linux-2023",
                            "install_state": "deployed",
                            "owner": "terraform",
                            "tags": {"role": "terraform", "provider": "aws", "appears_in": ["aws", "terraform"]},
                        },
                        source="terraform",
                    )
                except Exception:
                    pass
            elif rtype in (
                "azurerm_linux_virtual_machine",
                "azurerm_windows_virtual_machine",
                "azurerm_virtual_machine",
            ):
                from apps.vmware_sim import azure_engine as aze

                aze.get_state(session_id, "terraform-apply")
                aze.apply_action(
                    session_id,
                    "create_vm",
                    {"name": name, "size": "Standard_B2s", "location": "eastus"},
                )
            elif rtype == "google_compute_instance":
                from apps.vmware_sim import gcp_engine as gce

                gce.get_state(session_id, "terraform-apply")
                gce.apply_action(
                    session_id,
                    "create_instance",
                    {"name": name, "machine_type": "e2-medium", "zone": "us-central1-a"},
                )
            elif rtype == "vsphere_virtual_machine":
                from apps.vmware_sim import engine as ve

                ve.get_state(session_id, "terraform-apply")
                inv = (ve.get_state(session_id) or {}).get("inventory") or {}
                existing = [
                    v for v in (inv.get("vms") or [])
                    if (v.get("name") or "") == name
                ]
                if not existing:
                    # create_vm is idempotent-by-name at the call site; engine
                    # rejects duplicates with ok=False — we skip when present.
                    res = ve.apply_action(
                        session_id,
                        "create_vm",
                        {
                            "name": name,
                            "cpu": 2,
                            "memory_mb": 4096,
                            "disk_gb": 40,
                            "guest_os": "Ubuntu Linux (64-bit)",
                            "annotation": "Managed by Terraform",
                        },
                    )
                    if res.get("ok"):
                        try:
                            ve.apply_action(
                                session_id,
                                "power_on",
                                {"vm_name": name},
                            )
                        except Exception:
                            pass
                try:
                    from apps.labs.provisioner.simulation.server_identity import upsert_server

                    upsert_server(
                        session_id,
                        {
                            "id": f"tf-vsphere-{name}",
                            "hostname": f"{name}.fixitlab.local",
                            "primary_ip": "10.20.30.50",
                            "power": "on",
                            "os": "ubuntu-22.04",
                            "install_state": "deployed",
                            "owner": "terraform",
                            "tags": {
                                "role": "terraform",
                                "provider": "vmware",
                                "appears_in": ["vmware", "terraform"],
                            },
                        },
                        source="terraform",
                    )
                except Exception:
                    pass
            elif rtype == "maas_machine":
                from apps.vmware_sim import baremetal_engine as be

                be.get_state(session_id, "terraform-apply")
                be.apply_action(session_id, "login", {"user": "terraform"})
                machines = (
                    ((be.get_state(session_id) or {}).get("state") or {})
                    .get("maas", {})
                    .get("machines")
                    or []
                )
                if not any((m.get("hostname") or "") == name for m in machines):
                    be.apply_action(
                        session_id,
                        "maas_enlist",
                        {"hostname": name},
                    )
                try:
                    from apps.labs.provisioner.simulation.server_identity import upsert_server

                    upsert_server(
                        session_id,
                        {
                            "id": f"tf-maas-{name}",
                            "hostname": name,
                            "primary_ip": "",
                            "power": "off",
                            "os": "",
                            "install_state": "new",
                            "owner": "terraform",
                            "tags": {
                                "role": "terraform",
                                "provider": "maas",
                                "appears_in": ["maas", "baremetal", "terraform"],
                            },
                        },
                        source="terraform",
                    )
                except Exception:
                    pass
            elif rtype in ("lxd_instance", "lxd_container"):
                from apps.vmware_sim import baremetal_engine as be

                be.get_state(session_id, "terraform-apply")
                be.apply_action(session_id, "login", {"user": "terraform"})
                containers = (
                    ((be.get_state(session_id) or {}).get("state") or {})
                    .get("lxd", {})
                    .get("containers")
                    or []
                )
                if not any((c.get("name") or "") == name for c in containers):
                    be.apply_action(
                        session_id,
                        "create_lxd",
                        {"name": name, "image": "ubuntu:22.04"},
                    )
            elif rtype == "maas_tag":
                from apps.vmware_sim import baremetal_engine as be

                be.get_state(session_id, "terraform-apply")
                be.apply_action(session_id, "login", {"user": "terraform"})
                be.apply_action(
                    session_id,
                    "maas_tag_machine",
                    {"tag": r.get("tag") or name},
                )
            elif rtype == "maas_instance":
                from apps.vmware_sim import baremetal_engine as be

                be.get_state(session_id, "terraform-apply")
                be.apply_action(session_id, "login", {"user": "terraform"})
                bm_state = ((be.get_state(session_id) or {}).get("state") or {})
                machines = bm_state.get("maas", {}).get("machines") or []
                machine = next((m for m in machines if (m.get("hostname") or "") == name), None)
                if machine is None:
                    enlisted = be.apply_action(session_id, "maas_enlist", {"hostname": name})
                    mid = enlisted.get("machine_id")
                    if mid is not None:
                        be.apply_action(session_id, "maas_commission", {"machine_id": mid})
                elif machine.get("status") == "Ready":
                    be.apply_action(session_id, "maas_deploy", {"machine_id": machine.get("id")})
                elif machine.get("status") in ("New", "Failed", "Failed commissioning"):
                    be.apply_action(session_id, "maas_commission", {"machine_id": machine.get("id")})
            elif rtype in ("maas_vlan", "maas_subnet"):
                from apps.vmware_sim import baremetal_engine as be

                be.get_state(session_id, "terraform-apply")
                be.apply_action(session_id, "login", {"user": "terraform"})
                be.apply_action(
                    session_id,
                    "maas_add_subnet",
                    {"space": r.get("space") or "default", "subnet": r.get("cidr") or r.get("subnet")},
                )
        except Exception:
            continue
    return {k: v for k, v in links.items() if v}


def _mirror_destroy_to_clouds(session_id: str, resources: list[dict]) -> dict[str, bool]:
    """Terraform destroy → terminate/delete mirrored AWS/Azure/GCP/VMware/MAAS/LXD resources."""
    links = _cloud_links_from_resources(resources)
    for r in resources:
        rtype = str(r.get("type") or "")
        name = str(r.get("name") or "web")
        try:
            if rtype == "aws_instance":
                from apps.vmware_sim import aws_engine as ae

                host = name if name != "web" else "web-server"
                aws_st = ae.get_state(session_id, "terraform-destroy")
                live = [
                    i for i in (aws_st.get("state") or {}).get("instances") or []
                    if (
                        i.get("name") == host
                        or (i.get("tags") or {}).get("Name") == host
                        or i.get("name") == name
                    )
                    and (i.get("state") or "") != "terminated"
                ]
                for inst in live:
                    ae.apply_action(
                        session_id,
                        "terminate_instance",
                        {"instance_id": inst.get("id") or inst.get("name")},
                    )
            elif rtype in (
                "azurerm_linux_virtual_machine",
                "azurerm_windows_virtual_machine",
                "azurerm_virtual_machine",
            ):
                from apps.vmware_sim import azure_engine as aze

                aze.get_state(session_id, "terraform-destroy")
                aze.apply_action(session_id, "delete_vm", {"name": name})
            elif rtype == "google_compute_instance":
                from apps.vmware_sim import gcp_engine as gce

                gce.get_state(session_id, "terraform-destroy")
                gce.apply_action(session_id, "delete_instance", {"name": name})
            elif rtype == "vsphere_virtual_machine":
                from apps.vmware_sim import engine as ve

                ve.get_state(session_id, "terraform-destroy")
                # Must power off before delete_vm
                try:
                    ve.apply_action(session_id, "power_off", {"vm_name": name})
                except Exception:
                    pass
                ve.apply_action(session_id, "delete_vm", {"vm_name": name})
            elif rtype == "maas_machine":
                from apps.vmware_sim import baremetal_engine as be

                be.get_state(session_id, "terraform-destroy")
                be.apply_action(session_id, "login", {"user": "terraform"})
                be.apply_action(session_id, "maas_delete", {"hostname": name})
            elif rtype in ("lxd_instance", "lxd_container"):
                from apps.vmware_sim import baremetal_engine as be

                be.get_state(session_id, "terraform-destroy")
                be.apply_action(session_id, "login", {"user": "terraform"})
                be.apply_action(session_id, "delete_lxd", {"name": name})
        except Exception:
            continue
    return {k: v for k, v in links.items() if v}


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
        try:
            config = parse_hcl_files(files)
        except HCLParseError as exc:
            return {
                "ok": False,
                "output": f"Error: Invalid configuration\n\n  on {exc}\n",
                "error": "Configuration invalid",
            }
        if not config["resources"] and not config["data"]:
            return {
                "ok": False,
                "output": "Error: No resources or data sources declared",
                "error": "Configuration invalid",
            }
        graph = build_dependency_graph(config)
        if graph["cycles"]:
            cycle = ", ".join(graph["cycles"][0])
            return {
                "ok": False,
                "output": f"Error: Cycle: {cycle}\n",
                "error": "Configuration invalid",
            }
        out = "Success! The configuration is valid.\n"
        state["events"].insert(0, {"time": _now_iso(), "message": "Configuration validated", "severity": "info"})
        _save(session_id, entry)
        return {"ok": True, "output": out}

    if action == "terraform_plan":
        if not tf.get("initialized"):
            return {"ok": False, "error": f"Run {tool.lower()} init first"}
        if broken.get("stale_lock"):
            return {"ok": False, "error": "Error: state lock held — run force-unlock first", "output": "Error acquiring the state lock\n\nLock ID: fixitlab-lock\n"}
        try:
            config = parse_hcl_files(files)
        except HCLParseError as exc:
            # Fail CLOSED: an unparseable config must not produce a passing plan.
            tf["last_plan"] = None
            _save(session_id, entry)
            return {
                "ok": False,
                "error": "Configuration invalid",
                "output": f"Error: Invalid configuration\n\n  on {exc}\n",
            }
        graph = build_dependency_graph(config)
        if graph["cycles"]:
            tf["last_plan"] = None
            _save(session_id, entry)
            cycle = ", ".join(graph["cycles"][0])
            return {"ok": False, "error": "Cycle detected", "output": f"Error: Cycle: {cycle}\n"}
        errors = data_source_errors(config, tf.get("state_file") or empty_state())
        if errors:
            tf["last_plan"] = None
            _save(session_id, entry)
            return {"ok": False, "error": errors[0], "output": "\n".join(errors) + "\n"}

        tf_state = tf.get("state_file") or empty_state()
        computed = compute_plan(config, tf_state, graph)
        parsed = [
            {"type": n["type"], "name": n["name"]} for n in (config["resources"] or {}).values()
        ]
        plan = {
            "add": computed["add"],
            "change": computed["change"],
            "destroy": computed["destroy"],
            "replace": computed["replace"],
            "summary": computed["summary"],
            "actions": computed["actions"],
            "cloud_links": _cloud_links_from_resources(parsed),
        }
        tf["last_plan"] = plan
        tf["graph"] = {"order": graph["order"], "edges": graph["edges"]}
        tf["drift_detected"] = bool(computed["change"] or computed["replace"])
        broken["plan_required"] = False
        out = _format_plan_output(tool, files, plan, slug)
        state["events"].insert(0, {"time": _now_iso(), "message": plan["summary"], "severity": "info"})
        _save(session_id, entry)
        return {"ok": True, "plan": plan, "output": out}

    if action == "terraform_apply":
        if not tf.get("last_plan"):
            return {"ok": False, "error": f"Run {tool.lower()} plan first"}
        tf["last_apply"] = _now_iso()
        broken.pop("drift", None)
        broken.pop("stale_lock", None)
        main = files.get("main.tf", "")
        last_plan = tf.get("last_plan") or {}
        outputs: dict[str, Any] = {}
        try:
            config = parse_hcl_files(files)
        except HCLParseError as exc:
            return {
                "ok": False,
                "error": "Configuration invalid",
                "output": f"Error: Invalid configuration\n\n  on {exc}\n",
            }
        if last_plan.get("actions") is not None:
            prior_state = tf.get("state_file") or empty_state()
            new_state = apply_plan_to_state(config, prior_state, last_plan)
            tf["state_file"] = new_state
            outputs = compute_outputs(config, new_state)
            tf["outputs"] = outputs
            resources = [
                {"type": e["type"], "name": e["name"], "status": "applied"}
                for e in new_state.get("resources", {}).values()
                if e.get("mode") == "managed"
            ]
        else:
            hcl_blob = "\n".join(str(v) for v in files.values() if isinstance(v, str))
            resources = _parse_tf_resources(hcl_blob or main)
        if not resources:
            # Preserve legacy default so empty workspaces still complete labs.
            resources = [{"type": "aws_instance", "name": "web", "status": "applied"}]
        for r in resources:
            r["status"] = "applied"
        tf["resources"] = resources
        # Drift is now derived: after apply, state matches config by construction.
        tf["drift_detected"] = False
        cloud_links = _mirror_apply_to_clouds(str(session_id), resources)
        tf["cloud_links"] = cloud_links
        out = _format_apply_output(tool, tf, last_plan, outputs)
        if cloud_links:
            providers = ", ".join(sorted(k.upper() for k, v in cloud_links.items() if v))
            out = f"{out}\n\nCloud consoles updated: {providers}\nOpen AWS / Azure / GCP / VMware from the lab toolbar to verify."
        state["events"].insert(
            0,
            {"time": _now_iso(), "message": "Apply complete! Resources provisioned.", "severity": "success"},
        )
        _save(session_id, entry)
        return {"ok": True, "message": "Apply complete", "output": out, "cloud_links": cloud_links}

    if action == "terraform_destroy":
        if not tf.get("initialized"):
            return {"ok": False, "error": f"Run {tool.lower()} init first"}
        resources = list(tf.get("resources") or [])
        if not resources:
            hcl_blob = "\n".join(str(v) for v in files.values() if isinstance(v, str))
            resources = _parse_tf_resources(hcl_blob) or [
                {"type": "aws_instance", "name": "web", "status": "applied"}
            ]
        # Destroy runs the dependency graph in reverse: dependents die first.
        order = list((tf.get("graph") or {}).get("order") or [])
        if order:
            rank = {addr: idx for idx, addr in enumerate(order)}
            resources.sort(
                key=lambda r: -rank.get(f"{r.get('type')}.{r.get('name')}", -1)
            )
        prevented = []
        try:
            config_d = parse_hcl_files(files)
            for addr, node in (config_d.get("resources") or {}).items():
                if lifecycle_of(node)["prevent_destroy"]:
                    prevented.append(addr)
        except HCLParseError:
            pass
        if prevented:
            return {
                "ok": False,
                "error": f"Instance cannot be destroyed: {prevented[0]}",
                "output": (
                    f"Error: Instance cannot be destroyed\n\n"
                    f"Resource {prevented[0]} has lifecycle.prevent_destroy set.\n"
                ),
            }
        cloud_links = _mirror_destroy_to_clouds(str(session_id), resources)
        destroyed_n = len(resources)
        for r in resources:
            r["status"] = "destroyed"
        tf["resources"] = []
        tf["last_destroy"] = _now_iso()
        tf["cloud_links"] = {}
        tf["last_plan"] = None
        tf["state_file"] = empty_state()
        tf["outputs"] = {}
        lines = [
            f"{tool} destroy — auto-approving",
            "",
        ]
        for r in resources:
            lines.append(f"{r.get('type')}.{r.get('name')}: Destroying...")
            lines.append(f"{r.get('type')}.{r.get('name')}: Destruction complete")
        lines.extend([
            "",
            f"Destroy complete! Resources: {destroyed_n} destroyed.",
        ])
        if cloud_links:
            providers = ", ".join(sorted(k.upper() for k, v in cloud_links.items() if v))
            lines.append(f"\nCloud consoles updated: {providers} (resources removed)")
        out = "\n".join(lines)
        state["events"].insert(
            0,
            {"time": _now_iso(), "message": f"Destroy complete! {destroyed_n} resources destroyed.", "severity": "warning"},
        )
        _save(session_id, entry)
        return {
            "ok": True,
            "message": "Destroy complete",
            "output": out,
            "cloud_links": cloud_links,
            "destroyed": destroyed_n,
        }

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
