"""In-memory networking state (BGP, NTP, MTU) + VyOS candidate/running config."""

from __future__ import annotations

import copy
import re
import time
from typing import Any


_DEFAULT_VYOS_RUNNING = """\
interfaces {
    ethernet eth0 {
        address 10.64.1.1/24
        description management
    }
    ethernet eth1 {
        address 10.64.12.1/24
        description pxe-provision
    }
}
service {
    dhcp-server {
        shared-network-name pxe {
            subnet 10.64.12.0/24 {
                default-router 10.64.12.1
                bootfile-name undionly.kpxe
                bootfile-server 10.64.1.2
            }
        }
    }
}
"""

_DEFAULT_TREE: dict[str, Any] = {
    "interfaces": {
        "ethernet": {
            "eth0": {"address": "10.64.1.1/24", "description": "management"},
            "eth1": {"address": "10.64.12.1/24", "description": "pxe-provision"},
        }
    },
    "service": {
        "dhcp-server": {
            "shared-network-name": {
                "pxe": {
                    "subnet": {
                        "10.64.12.0/24": {
                            "default-router": "10.64.12.1",
                            "bootfile-name": "undionly.kpxe",
                            "bootfile-server": "10.64.1.2",
                        }
                    }
                }
            }
        }
    },
}

_DEFAULT_DHCP_LEASES = [
    {
        "ip": "10.64.12.11",
        "mac": "a4:bb:6d:aa:01:01",
        "expires": "2026/08/01 12:00:00",
        "pool": "pxe-pool",
        "client": "gpu-node-01",
    },
    {
        "ip": "10.64.12.12",
        "mac": "a4:bb:6d:aa:01:02",
        "expires": "2026/08/01 12:00:00",
        "pool": "pxe-pool",
        "client": "gpu-node-02",
    },
]

# Leaf keys that take the following token as a scalar value (VyOS set style).
_SCALAR_LEAVES = frozenset({
    "address", "description", "mtu", "hw-id", "mac", "remote-as", "peer-group",
    "local-as", "update-source", "route-map", "password", "ttl", "network",
    "nexthop", "next-hop", "distance", "area", "router-id", "hello-interval",
    "dead-interval", "priority", "action", "protocol", "destination", "source",
    "destination-port", "source-port", "state", "log",
    "interface", "inbound-interface", "outbound-interface", "translation", "exclude",
    "vrid", "virtual-address", "advertise-interval", "preempt", "sync-group",
    "default-router", "bootfile-name", "bootfile-server", "dns-server",
    "domain-name", "lease", "start", "stop", "subnet-id", "static-mapping",
    "listen-address", "allow-from", "port", "listen", "server", "address-family",
    "private-key", "public-key", "allowed-ips", "endpoint", "peer", "mode",
    "local-address", "remote", "ike-group", "esp-group", "tunnel",
    "route-type", "set", "table", "rule", "default-action", "zone",
})


def _tree_set(tree: dict, tokens: list[str]) -> None:
    """Apply a VyOS-style set path into a nested dict."""
    if not tokens:
        return
    # Find last scalar leaf; everything after it is the value (joined).
    value_idx = None
    for i, tok in enumerate(tokens):
        if tok in _SCALAR_LEAVES and i + 1 < len(tokens):
            value_idx = i
    if value_idx is not None:
        path = tokens[:value_idx]
        leaf = tokens[value_idx]
        value: Any = " ".join(tokens[value_idx + 1 :])
        # Coerce integers where obvious.
        if isinstance(value, str) and value.isdigit():
            value = int(value)
        node = tree
        for p in path:
            if p not in node or not isinstance(node[p], dict):
                node[p] = {}
            node = node[p]
        node[leaf] = value
        return
    # Presence / container path (e.g. set protocols bgp 65001)
    node = tree
    for i, tok in enumerate(tokens):
        if i == len(tokens) - 1:
            if tok not in node:
                node[tok] = {}
            elif not isinstance(node[tok], dict):
                node[tok] = {"_value": node[tok]}
            return
        if tok not in node or not isinstance(node[tok], dict):
            node[tok] = {}
        node = node[tok]


def _tree_delete(tree: dict, tokens: list[str]) -> None:
    if not tokens or not isinstance(tree, dict):
        return
    node = tree
    for tok in tokens[:-1]:
        if tok not in node or not isinstance(node[tok], dict):
            return
        node = node[tok]
    node.pop(tokens[-1], None)


def _tree_get(tree: dict, tokens: list[str]) -> Any:
    node: Any = tree
    for tok in tokens:
        if not isinstance(node, dict) or tok not in node:
            return None
        node = node[tok]
    return node


def _render_tree(tree: dict, indent: int = 0) -> str:
    """Render nested dict as VyOS-ish curly config text."""
    lines: list[str] = []
    pad = "    " * indent

    def walk(node: dict, level: int) -> None:
        p = "    " * level
        for key, val in node.items():
            if key.startswith("_"):
                continue
            if isinstance(val, dict):
                if not val:
                    lines.append(f"{p}{key} {{}}")
                elif all(not isinstance(v, dict) for v in val.values()):
                    lines.append(f"{p}{key} {{")
                    for lk, lv in val.items():
                        if lk.startswith("_"):
                            continue
                        lines.append(f"{p}    {lk} {lv}")
                    lines.append(f"{p}}}")
                else:
                    lines.append(f"{p}{key} {{")
                    walk(val, level + 1)
                    lines.append(f"{p}}}")
            else:
                lines.append(f"{p}{key} {val}")

    walk(tree, indent)
    return "\n".join(lines) + ("\n" if lines else "")


def _collect_bgp_neighbors_from_tree(tree: dict) -> list[dict]:
    out: list[dict] = []
    bgp = _tree_get(tree, ["protocols", "bgp"]) or {}
    if not isinstance(bgp, dict):
        return out
    for asn_key, asn_body in bgp.items():
        if not isinstance(asn_body, dict):
            continue
        neighbors = asn_body.get("neighbor") or {}
        if not isinstance(neighbors, dict):
            continue
        for ip, nb in neighbors.items():
            if not isinstance(nb, dict):
                nb = {}
            remote_as = nb.get("remote-as")
            out.append({
                "neighbor": ip,
                "remote_as": int(remote_as) if remote_as is not None else None,
                "local_as": int(asn_key) if str(asn_key).isdigit() else asn_key,
                "state": "Idle" if remote_as is None else "Established",
                "prefixes": 0 if remote_as is None else 42,
            })
    return out


def _validate_candidate_tree(tree: dict) -> str | None:
    """Return a realistic VyOS commit error, or None if valid."""
    bgp = _tree_get(tree, ["protocols", "bgp"]) or {}
    if not isinstance(bgp, dict):
        return None
    for asn_key, asn_body in bgp.items():
        if not isinstance(asn_body, dict):
            continue
        neighbors = asn_body.get("neighbor") or {}
        if not isinstance(neighbors, dict):
            continue
        for ip, nb in neighbors.items():
            if not isinstance(nb, dict):
                nb = {}
            if nb.get("remote-as") is None and nb.get("peer-group") is None:
                return (
                    f"Validation failed for: protocols bgp {asn_key} neighbor {ip}\n"
                    f"  Must configure 'remote-as' or 'peer-group' for neighbor\n"
                    f"Commit failed"
                )
    return None


class NetworkingState:
    def __init__(self, scenario_slug: str = "") -> None:
        self.scenario_slug = scenario_slug.lower()
        self.bgp_neighbors = [
            {"neighbor": "10.0.0.2", "remote_as": 65001, "state": "Established", "prefixes": 142},
        ]
        self.ntp_synced = True
        self.interface_mtu = 1500
        # VyOS-style dual config: candidate edits land on commit; rollback restores.
        self.vyos_running = _DEFAULT_VYOS_RUNNING
        self.vyos_candidate = copy.deepcopy(self.vyos_running)
        self.vyos_configure_mode = False
        self.vyos_history: list[str] = [self.vyos_running]
        self.vyos_tree: dict[str, Any] = copy.deepcopy(_DEFAULT_TREE)
        self.vyos_running_tree: dict[str, Any] = copy.deepcopy(_DEFAULT_TREE)
        self.vyos_candidate_tree: dict[str, Any] = copy.deepcopy(_DEFAULT_TREE)
        self.vyos_edit_path: list[str] = []
        self.revision: int = 0
        self.commit_confirm_deadline: float | None = None
        self.commit_confirm_seconds: int | None = None
        self._confirm_snapshot_running: str | None = None
        self._confirm_snapshot_tree: dict | None = None
        self.vyos_firewall_rules: list[str] = []
        self.vyos_vrrp: bool = False
        self.vyos_nat: bool = False
        self.dhcp_leases: list[dict] = copy.deepcopy(_DEFAULT_DHCP_LEASES)
        self.firewall_counters: dict[str, dict] = {}
        self._shell_state = None  # optional RHELOSState for save/load
        self._apply_scenario()

    def bind_shell(self, shell_state) -> None:
        self._shell_state = shell_state

    def _apply_scenario(self) -> None:
        s = self.scenario_slug
        if "bgp" in s:
            self.bgp_neighbors = [
                {"neighbor": "10.0.0.2", "remote_as": 65002, "state": "Idle", "prefixes": 0},
            ]
        elif "ntp" in s:
            self.ntp_synced = False
        elif "mtu" in s:
            self.interface_mtu = 9000

    def bgp_summary(self) -> str:
        lines = ["Neighbor        V    AS   State       Prefixes"]
        for n in self.bgp_neighbors:
            asn = n.get("remote_as")
            asn_s = str(asn) if asn is not None else "-"
            lines.append(
                f"{n['neighbor']:<15} 4 {asn_s:<5} {n['state']:<11} {n['prefixes']}"
            )
        return "\n".join(lines)

    def fix_bgp(self, remote_as: int = 65001) -> str:
        for n in self.bgp_neighbors:
            n["remote_as"] = remote_as
            n["state"] = "Established"
            n["prefixes"] = 142
        return "BGP neighbor configured"

    def chrony_tracking(self) -> str:
        if self.ntp_synced:
            return (
                "Reference ID    : C0A80101 (ntp.fixitlab.local)\n"
                "Stratum         : 2\n"
                "System time     : synced"
            )
        return "Reference ID    : 00000000 ()\nLeap status     : Not synchronized"

    def sync_ntp(self) -> str:
        self.ntp_synced = True
        return "NTP synchronized"

    def is_healthy(self) -> bool:
        if any(n["state"] != "Established" for n in self.bgp_neighbors):
            return False
        if not self.ntp_synced:
            return False
        return True

    # ── Config-mode helpers ────────────────────────────────────────────────
    def _prompt_edit(self) -> str:
        if self.vyos_edit_path:
            return f"[edit {' '.join(self.vyos_edit_path)}]"
        return "[edit]"

    def _resolve_path(self, path: str) -> str:
        path = (path or "").strip()
        if self.vyos_edit_path and path and not path.startswith("interfaces") and not path.startswith("protocols"):
            # Relative path under current edit context
            return " ".join(self.vyos_edit_path) + " " + path
        if self.vyos_edit_path and not path:
            return " ".join(self.vyos_edit_path)
        return path

    def _sync_tree_alias(self) -> None:
        """Keep self.vyos_tree pointing at the active working tree."""
        if self.vyos_configure_mode:
            self.vyos_tree = self.vyos_candidate_tree
        else:
            self.vyos_tree = self.vyos_running_tree

    def _maybe_auto_rollback(self) -> str | None:
        if self.commit_confirm_deadline is None:
            return None
        if time.time() < self.commit_confirm_deadline:
            return None
        # Deadline passed — restore pre-confirm snapshot.
        if self._confirm_snapshot_running is not None:
            self.vyos_running = self._confirm_snapshot_running
            self.vyos_candidate = self._confirm_snapshot_running
        if self._confirm_snapshot_tree is not None:
            self.vyos_running_tree = copy.deepcopy(self._confirm_snapshot_tree)
            self.vyos_candidate_tree = copy.deepcopy(self._confirm_snapshot_tree)
        self.commit_confirm_deadline = None
        self.commit_confirm_seconds = None
        self._confirm_snapshot_running = None
        self._confirm_snapshot_tree = None
        self._sync_from_running_tree()
        self._sync_tree_alias()
        return "Commit confirm expired — configuration rolled back"

    def _sync_from_running_tree(self) -> None:
        """Refresh derived runtime views from committed tree."""
        tree_nbs = _collect_bgp_neighbors_from_tree(self.vyos_running_tree)
        if tree_nbs:
            # Merge with existing display neighbors (preserve scenario peers when tree empty of overlap).
            by_ip = {n["neighbor"]: n for n in self.bgp_neighbors}
            for n in tree_nbs:
                by_ip[n["neighbor"]] = n
            self.bgp_neighbors = list(by_ip.values())
        fw = _tree_get(self.vyos_running_tree, ["firewall"]) or {}
        if isinstance(fw, dict):
            for name_key in ("name", "zone"):
                names = fw.get(name_key) or {}
                if isinstance(names, dict):
                    for fname in names:
                        key = f"{name_key}/{fname}"
                        self.firewall_counters.setdefault(
                            key, {"packets": 0, "bytes": 0, "rules": 0}
                        )
                        body = names[fname]
                        if isinstance(body, dict):
                            rules = body.get("rule") or {}
                            self.firewall_counters[key]["rules"] = (
                                len(rules) if isinstance(rules, dict) else 0
                            )
                            self.firewall_counters[key]["packets"] = max(
                                self.firewall_counters[key]["packets"],
                                self.firewall_counters[key]["rules"] * 12,
                            )
                            self.firewall_counters[key]["bytes"] = (
                                self.firewall_counters[key]["packets"] * 64
                            )

    # ── VyOS commit / rollback ─────────────────────────────────────────────
    def vyos_enter_configure(self) -> str:
        self.vyos_configure_mode = True
        self.vyos_candidate = (
            copy.deepcopy(self.vyos_running)
            if not isinstance(self.vyos_running, str)
            else self.vyos_running
        )
        self.vyos_candidate_tree = copy.deepcopy(self.vyos_running_tree)
        self.vyos_edit_path = []
        self._sync_tree_alias()
        return "[edit]"

    def vyos_exit_configure(self) -> str:
        self.vyos_configure_mode = False
        self.vyos_candidate = self.vyos_running
        self.vyos_candidate_tree = copy.deepcopy(self.vyos_running_tree)
        self.vyos_edit_path = []
        self._sync_tree_alias()
        return "exit"

    def vyos_edit(self, path: str) -> str:
        if not self.vyos_configure_mode:
            return "Error: configuration path is not open — run 'configure' first"
        tokens = (path or "").strip().split()
        if not tokens:
            return self._prompt_edit()
        self.vyos_edit_path = tokens
        return self._prompt_edit()

    def vyos_up(self) -> str:
        if not self.vyos_configure_mode:
            return "Error: configuration path is not open — run 'configure' first"
        if self.vyos_edit_path:
            self.vyos_edit_path = self.vyos_edit_path[:-1]
        return self._prompt_edit()

    def vyos_top(self) -> str:
        if not self.vyos_configure_mode:
            return "Error: configuration path is not open — run 'configure' first"
        self.vyos_edit_path = []
        return "[edit]"

    def vyos_set(self, path: str) -> str:
        if not self.vyos_configure_mode:
            return "Error: configuration path is not open — run 'configure' first"
        path = self._resolve_path(path)
        path = (path or "").strip()
        if not path:
            return "Error: incomplete command"
        marker = f"    # set {path}\n"
        if marker not in self.vyos_candidate:
            if self.vyos_candidate.rstrip().endswith("}"):
                body = self.vyos_candidate.rstrip()[:-1]
                self.vyos_candidate = f"{body}{marker}}}\n"
            else:
                self.vyos_candidate = f"{self.vyos_candidate.rstrip()}\n{marker}"
        tokens = path.split()
        _tree_set(self.vyos_candidate_tree, tokens)
        self._sync_tree_alias()
        low = path.lower()
        if "protocols bgp" in low and "neighbor" in low:
            m = re.search(r"neighbor\s+(\d+\.\d+\.\d+\.\d+)", low)
            asn = re.search(r"remote-as\s+(\d+)", low)
            if m:
                ip = m.group(1)
                found = False
                for n in self.bgp_neighbors:
                    if n["neighbor"] == ip:
                        if asn:
                            n["remote_as"] = int(asn.group(1))
                        found = True
                if not found:
                    self.bgp_neighbors.append({
                        "neighbor": ip,
                        "remote_as": int(asn.group(1)) if asn else None,
                        "state": "Idle",
                        "prefixes": 0,
                    })
        if "firewall" in low or "firewall name" in low:
            if path not in self.vyos_firewall_rules:
                self.vyos_firewall_rules.append(path)
        if "high-availability vrrp" in low or "vrrp" in low:
            self.vyos_vrrp = True
        if "nat" in low and ("source" in low or "destination" in low or "rule" in low):
            self.vyos_nat = True
        return ""

    def vyos_delete(self, path: str) -> str:
        if not self.vyos_configure_mode:
            return "Error: configuration path is not open — run 'configure' first"
        path = self._resolve_path(path)
        path = (path or "").strip()
        marker = f"    # set {path}\n"
        self.vyos_candidate = self.vyos_candidate.replace(marker, "")
        # Also strip markers that are prefixes of deleted path
        tokens = path.split()
        _tree_delete(self.vyos_candidate_tree, tokens)
        self._sync_tree_alias()
        if path in self.vyos_firewall_rules:
            self.vyos_firewall_rules.remove(path)
        return ""

    def vyos_compare(self) -> str:
        """Diff candidate vs running — mirrors VyOS `compare` in configure mode."""
        if not self.vyos_configure_mode:
            return "Error: configuration path is not open — run 'configure' first"
        if self.vyos_candidate == self.vyos_running and self.vyos_candidate_tree == self.vyos_running_tree:
            return "No changes between working and active configurations"
        run_lines = self.vyos_running.splitlines()
        cand_lines = self.vyos_candidate.splitlines()
        run_set = set(run_lines)
        cand_set = set(cand_lines)
        added = [ln for ln in cand_lines if ln not in run_set and ln.strip()]
        removed = [ln for ln in run_lines if ln not in cand_set and ln.strip()]
        out = [self._prompt_edit(), ""]
        for ln in removed:
            out.append(f"- {ln}")
        for ln in added:
            out.append(f"+ {ln}")
        if len(out) == 2:
            # Tree-only changes — render compact set markers from tree walk
            out.append("(configuration tree differs)")
        return "\n".join(out)

    def vyos_commit(self, confirm_minutes: int | None = None) -> str:
        notice = self._maybe_auto_rollback()
        if not self.vyos_configure_mode:
            return "Error: configuration path is not open — run 'configure' first"
        err = _validate_candidate_tree(self.vyos_candidate_tree)
        if err:
            return err
        if (
            self.vyos_candidate == self.vyos_running
            and self.vyos_candidate_tree == self.vyos_running_tree
        ):
            return "No configuration changes to commit"
        # Snapshot for history / rollback
        self.vyos_history.append(self.vyos_running)
        if len(self.vyos_history) > 10:
            self.vyos_history = self.vyos_history[-10:]
        prev_running = self.vyos_running
        prev_tree = copy.deepcopy(self.vyos_running_tree)
        # Apply atomically
        self.vyos_running = self.vyos_candidate
        self.vyos_running_tree = copy.deepcopy(self.vyos_candidate_tree)
        self.revision += 1
        self._sync_from_running_tree()
        for n in self.bgp_neighbors:
            if n.get("remote_as") is not None and n.get("state") == "Idle":
                n["state"] = "Established"
                n["prefixes"] = max(n.get("prefixes") or 0, 42)
        self._sync_tree_alias()
        msg = f"{self._prompt_edit()}\nCommit complete."
        if confirm_minutes is not None and confirm_minutes > 0:
            self._confirm_snapshot_running = prev_running
            self._confirm_snapshot_tree = prev_tree
            self.commit_confirm_seconds = int(confirm_minutes) * 60
            self.commit_confirm_deadline = time.time() + self.commit_confirm_seconds
            msg += (
                f"\ncommit confirm will reboot system in {confirm_minutes} minutes"
                f" unless confirmed"
            )
        if notice:
            msg = notice + "\n" + msg
        return msg

    def vyos_commit_confirm(self, minutes: int = 10) -> str:
        return self.vyos_commit(confirm_minutes=max(1, int(minutes or 10)))

    def vyos_confirm(self) -> str:
        if self.commit_confirm_deadline is None:
            return "No commit confirm pending"
        self.commit_confirm_deadline = None
        self.commit_confirm_seconds = None
        self._confirm_snapshot_running = None
        self._confirm_snapshot_tree = None
        return "Commit confirm completed"

    def vyos_discard(self) -> str:
        if not self.vyos_configure_mode:
            return "Error: configuration path is not open — run 'configure' first"
        self.vyos_candidate = self.vyos_running
        self.vyos_candidate_tree = copy.deepcopy(self.vyos_running_tree)
        self._sync_tree_alias()
        return f"{self._prompt_edit()}\nChanges have been discarded"

    def vyos_save(self, shell_state=None) -> str:
        st = shell_state or self._shell_state
        boot = self._render_config_boot()
        if st is not None and hasattr(st, "_write_file"):
            try:
                st._write_file("/config/config.boot", boot)
            except Exception:
                pass
        return "Saving configuration to '/config/config.boot'...\nDone"

    def vyos_load(self, shell_state=None) -> str:
        st = shell_state or self._shell_state
        content = None
        if st is not None and hasattr(st, "read_file"):
            try:
                content = st.read_file("/config/config.boot")
            except Exception:
                content = None
        if not content:
            return "Error: unable to load configuration file /config/config.boot"
        # Reload candidate from saved boot text; keep tree from running if we cannot parse.
        if self.vyos_configure_mode:
            self.vyos_candidate = content
        else:
            self.vyos_running = content
            self.vyos_candidate = content
        return "Loading configuration from '/config/config.boot'...\nDone"

    def _render_config_boot(self) -> str:
        body = _render_tree(self.vyos_running_tree)
        # Preserve marker lines from string config for labs that grep them.
        markers = [
            ln for ln in self.vyos_running.splitlines()
            if ln.strip().startswith("# set ")
        ]
        if markers:
            body = body.rstrip() + "\n" + "\n".join(markers) + "\n"
        return body

    def vyos_rollback(self, steps: int = 1) -> str:
        if not self.vyos_configure_mode:
            return "Error: configuration path is not open — run 'configure' first"
        steps = max(1, int(steps or 1))
        if not self.vyos_history:
            return "Error: no previous revision to roll back to"
        idx = max(0, len(self.vyos_history) - steps)
        restored = self.vyos_history[idx]
        self.vyos_candidate = restored
        self.vyos_running = restored
        # Best-effort: if restored equals a known default, reset tree; else keep last tree snapshot.
        if restored.strip() == _DEFAULT_VYOS_RUNNING.strip() or (
            "# set " not in restored and "ethernet eth0" in restored
        ):
            # Rebuild tree from markers in restored string when possible.
            self.vyos_running_tree = copy.deepcopy(_DEFAULT_TREE)
            self.vyos_candidate_tree = copy.deepcopy(_DEFAULT_TREE)
            for ln in restored.splitlines():
                s = ln.strip()
                if s.startswith("# set "):
                    _tree_set(self.vyos_running_tree, s[6:].split())
            self.vyos_candidate_tree = copy.deepcopy(self.vyos_running_tree)
        else:
            # Replay markers onto default tree
            self.vyos_running_tree = copy.deepcopy(_DEFAULT_TREE)
            for ln in restored.splitlines():
                s = ln.strip()
                if s.startswith("# set "):
                    _tree_set(self.vyos_running_tree, s[6:].split())
            self.vyos_candidate_tree = copy.deepcopy(self.vyos_running_tree)
        self.vyos_history = self.vyos_history[: idx + 1] if idx > 0 else []
        self.revision = max(0, self.revision - steps)
        self._sync_from_running_tree()
        self._sync_tree_alias()
        return f"[edit]\nRollback complete — restored revision -{steps}."

    def vyos_show_config(self, *, candidate: bool = False) -> str:
        if candidate or self.vyos_configure_mode:
            text = self.vyos_candidate
            tree = self.vyos_candidate_tree
        else:
            text = self.vyos_running
            tree = self.vyos_running_tree
        rendered = _render_tree(tree)
        markers = [ln for ln in text.splitlines() if ln.strip().startswith("# set ")]
        if markers:
            rendered = rendered.rstrip() + "\n" + "\n".join(markers) + "\n"
        return rendered or text

    def vyos_show_pending(self) -> str:
        if not self.vyos_configure_mode:
            return "Error: configuration path is not open — run 'configure' first"
        return self.vyos_compare()

    def vyos_show_history(self) -> str:
        if not self.vyos_history:
            return "No commits in revision history"
        lines = ["Revision history (newest last):"]
        for i, snap in enumerate(self.vyos_history, 1):
            preview = next(
                (ln.strip() for ln in snap.splitlines() if ln.strip().startswith("#")),
                "config",
            )
            lines.append(f"  {i}: {preview[:72]}")
        lines.append(f"  {len(self.vyos_history) + 1}: [running] rev {self.revision}")
        return "\n".join(lines)

    # ── Operational show commands (structured) ─────────────────────────────
    def show_interfaces(self) -> str:
        self._maybe_auto_rollback()
        lines = [
            "Codes: S - State, L - Link, u - Up, D - Down, A - Admin Down",
            "Interface        IP Address                        S/L  Description",
        ]
        eth = _tree_get(self.vyos_running_tree, ["interfaces", "ethernet"]) or {}
        if isinstance(eth, dict):
            for name, body in sorted(eth.items()):
                if not isinstance(body, dict):
                    continue
                addr = body.get("address") or "-"
                desc = body.get("description") or ""
                lines.append(f"{name:<16} {str(addr):<32} u/u  {desc}")
                vifs = body.get("vif") or {}
                if isinstance(vifs, dict):
                    for vid, vbody in sorted(vifs.items(), key=lambda x: str(x[0])):
                        if not isinstance(vbody, dict):
                            continue
                        vaddr = vbody.get("address") or "-"
                        vdesc = vbody.get("description") or ""
                        lines.append(f"{name}.{vid:<12} {str(vaddr):<32} u/u  {vdesc}")
        for kind in ("bond", "bridge"):
            group = _tree_get(self.vyos_running_tree, ["interfaces", kind]) or {}
            if isinstance(group, dict):
                for name, body in sorted(group.items()):
                    if not isinstance(body, dict):
                        continue
                    addr = body.get("address") or "-"
                    desc = body.get("description") or kind
                    lines.append(f"{name:<16} {str(addr):<32} u/u  {desc}")
        lines.append(f"{'lo':<16} {'127.0.0.1/8':<32} u/u")
        # Ensure baseline eth0/eth1 appear even if tree was wiped oddly
        if len(lines) <= 3:
            lines.extend([
                "eth0             10.64.1.1/24                      u/u  management",
                "eth1             10.64.12.1/24                     u/u  pxe-provision",
            ])
        return "\n".join(lines)

    def show_ip_route(self) -> str:
        self._maybe_auto_rollback()
        lines = [
            "Codes: K - kernel, C - connected, S - static, R - RIP, O - OSPF,",
            "       B - BGP, > - selected route, * - FIB route",
            "",
        ]
        eth = _tree_get(self.vyos_running_tree, ["interfaces", "ethernet"]) or {}
        if isinstance(eth, dict):
            for name, body in sorted(eth.items()):
                if not isinstance(body, dict):
                    continue
                addr = body.get("address")
                if not addr or "/" not in str(addr):
                    continue
                ip, prefix = str(addr).split("/", 1)
                # Connected network approximation
                parts = ip.split(".")
                if len(parts) == 4 and prefix.isdigit():
                    pfx = int(prefix)
                    if pfx >= 24:
                        net = f"{parts[0]}.{parts[1]}.{parts[2]}.0/{prefix}"
                    else:
                        net = f"{parts[0]}.{parts[1]}.0.0/{prefix}"
                    lines.append(f"C>* {net} is directly connected, {name}")
        static = _tree_get(self.vyos_running_tree, ["protocols", "static", "route"]) or {}
        if isinstance(static, dict):
            for prefix, body in sorted(static.items()):
                nh = "-"
                if isinstance(body, dict):
                    nh = body.get("next-hop") or body.get("nexthop") or "-"
                    if isinstance(nh, dict):
                        nh = next(iter(nh.keys()), "-")
                lines.append(f"S>* {prefix} [1/0] via {nh}")
        ospf = _tree_get(self.vyos_running_tree, ["protocols", "ospf"])
        if ospf:
            lines.append("O>* 10.64.0.0/16 [110/20] via 10.64.1.2, eth0")
        bgp_nets = _tree_get(self.vyos_running_tree, ["protocols", "bgp"])
        if bgp_nets and any(n.get("state") == "Established" for n in self.bgp_neighbors):
            lines.append("B>* 0.0.0.0/0 [20/0] via 10.0.0.2, eth0")
        if len(lines) <= 3:
            lines.append("C>* 10.64.1.0/24 is directly connected, eth0")
            lines.append("C>* 10.64.12.0/24 is directly connected, eth1")
        return "\n".join(lines)

    def show_ip_bgp_summary(self) -> str:
        self._maybe_auto_rollback()
        return self.bgp_summary()

    def show_vrrp(self) -> str:
        self._maybe_auto_rollback()
        vrrp = _tree_get(self.vyos_running_tree, ["high-availability", "vrrp"]) or {}
        if not vrrp and not self.vyos_vrrp:
            return "No VRRP groups configured"
        lines = [
            "RFC        Addr             Last        Transition",
            "Group Interface State  Priority  Time",
        ]
        groups = vrrp.get("group") if isinstance(vrrp, dict) else None
        if isinstance(groups, dict) and groups:
            for gname, body in groups.items():
                if not isinstance(body, dict):
                    body = {}
                iface = body.get("interface") or "eth0"
                if isinstance(iface, dict):
                    iface = next(iter(iface.keys()), "eth0")
                prio = body.get("priority") or 100
                if isinstance(prio, dict):
                    prio = next(iter(prio.keys()), 100)
                vaddr = body.get("virtual-address") or "-"
                if isinstance(vaddr, dict):
                    vaddr = next(iter(vaddr.keys()), "-")
                lines.append(
                    f"{str(gname):<10} {str(iface):<10} MASTER {str(prio):<9} 0:00:42  {vaddr}"
                )
        else:
            lines.append("pxe-ha     eth1       MASTER 150       0:01:12  10.64.12.254")
        return "\n".join(lines)

    def show_nat(self) -> str:
        self._maybe_auto_rollback()
        nat = _tree_get(self.vyos_running_tree, ["nat"]) or {}
        if not nat and not self.vyos_nat:
            return "No NAT rules configured"
        lines = ["Rule  Type   Intf     Translation              Description"]
        for kind in ("source", "destination"):
            section = nat.get(kind) if isinstance(nat, dict) else None
            rules = (section or {}).get("rule") if isinstance(section, dict) else None
            if isinstance(rules, dict):
                for rnum, body in sorted(rules.items(), key=lambda x: str(x[0])):
                    if not isinstance(body, dict):
                        body = {}
                    trans = body.get("translation") or body.get("address") or "-"
                    if isinstance(trans, dict):
                        trans = trans.get("address") or str(trans)
                    iface = body.get("outbound-interface") or body.get("inbound-interface") or "-"
                    desc = body.get("description") or ""
                    lines.append(f"{rnum:<5} {kind[:6]:<6} {str(iface):<8} {str(trans):<24} {desc}")
        if len(lines) == 1:
            lines.append("10    source eth1     masquerade              pxe-egress")
        return "\n".join(lines)

    def show_firewall(self) -> str:
        self._maybe_auto_rollback()
        fw = _tree_get(self.vyos_running_tree, ["firewall"]) or {}
        lines = ["-----------------------------", "Firewall Rulesets", "-----------------------------"]
        found = False
        if isinstance(fw, dict):
            for kind in ("name", "zone"):
                names = fw.get(kind) or {}
                if not isinstance(names, dict):
                    continue
                for fname, body in names.items():
                    found = True
                    ctr = self.firewall_counters.get(f"{kind}/{fname}", {})
                    lines.append(f"\n{kind} {fname}")
                    lines.append(
                        f"  packets: {ctr.get('packets', 0)}  bytes: {ctr.get('bytes', 0)}"
                    )
                    default = "-"
                    if isinstance(body, dict):
                        default = body.get("default-action") or "drop"
                        rules = body.get("rule") or {}
                        if isinstance(rules, dict):
                            for rnum, rbody in sorted(rules.items(), key=lambda x: str(x[0])):
                                action = "-"
                                proto = "all"
                                if isinstance(rbody, dict):
                                    action = rbody.get("action") or "-"
                                    proto = rbody.get("protocol") or "all"
                                lines.append(f"  {rnum:>4}  {action:<8} {proto}")
                    lines.append(f"  default-action: {default}")
        # Marker-based rules from labs
        if self.vyos_firewall_rules:
            found = True
            lines.append("\nConfigured paths:")
            for p in self.vyos_firewall_rules:
                lines.append(f"  set {p}")
        if not found:
            lines.append("(no firewall rulesets)")
        return "\n".join(lines)

    def show_dhcp_leases(self) -> str:
        self._maybe_auto_rollback()
        lines = [
            "IP address    Hardware address    Lease expiration     Pool      Client Name",
        ]
        for lease in self.dhcp_leases:
            lines.append(
                f"{lease['ip']:<13} {lease['mac']:<19} {lease['expires']:<20} "
                f"{lease['pool']:<9} {lease.get('client', '')}"
            )
        return "\n".join(lines)

    def show_version(self) -> str:
        return (
            "Version:          VyOS 1.4-rolling-fixitlab\n"
            "Release train:    sagitta\n"
            "Built by:         FixitLab Labs\n"
            "Built on:         Tue 06 Aug 2026 00:00 UTC\n"
            "Build UUID:       a1b2c3d4-e5f6-7890-abcd-ef1234567890\n"
            "Build commit ID:  fixitlab0\n"
            f"Configuration revision: {self.revision}\n"
            "Hardware vendor:  QEMU\n"
            "Hardware model:   Standard PC\n"
            "Hardware UUID:    00000000-0000-4000-8000-000000000001\n"
            "Hardware serial:  fixitlab-vyos-01"
        )

    def to_dashboard(self) -> dict:
        """Structured snapshot for the web ops dashboard."""
        self._maybe_auto_rollback()
        interfaces = []
        eth = _tree_get(self.vyos_running_tree, ["interfaces", "ethernet"]) or {}
        if isinstance(eth, dict):
            for name, body in sorted(eth.items()):
                if not isinstance(body, dict):
                    continue
                interfaces.append({
                    "name": name,
                    "address": body.get("address"),
                    "description": body.get("description") or "",
                    "state": "up",
                    "mtu": body.get("mtu") or self.interface_mtu,
                })
                vifs = body.get("vif") or {}
                if isinstance(vifs, dict):
                    for vid, vbody in vifs.items():
                        if not isinstance(vbody, dict):
                            continue
                        interfaces.append({
                            "name": f"{name}.{vid}",
                            "address": vbody.get("address"),
                            "description": vbody.get("description") or "",
                            "state": "up",
                            "mtu": vbody.get("mtu") or self.interface_mtu,
                        })
        routes = []
        for ln in self.show_ip_route().splitlines():
            if ln.startswith(("C>", "S>", "O>", "B>", "K>")):
                routes.append(ln)
        ospf = _tree_get(self.vyos_running_tree, ["protocols", "ospf"])
        uncommitted = (
            self.vyos_configure_mode
            and (
                self.vyos_candidate != self.vyos_running
                or self.vyos_candidate_tree != self.vyos_running_tree
            )
        )
        return {
            "interfaces": interfaces,
            "routes": routes,
            "bgp": copy.deepcopy(self.bgp_neighbors),
            "ospf": {"configured": bool(ospf), "areas": list((ospf or {}).get("area", {}).keys()) if isinstance(ospf, dict) else []},
            "firewall": {
                "rules": list(self.vyos_firewall_rules),
                "counters": copy.deepcopy(self.firewall_counters),
            },
            "nat": {"configured": bool(self.vyos_nat or _tree_get(self.vyos_running_tree, ["nat"]))},
            "vrrp": {
                "configured": bool(self.vyos_vrrp or _tree_get(self.vyos_running_tree, ["high-availability", "vrrp"])),
                "summary": self.show_vrrp() if (self.vyos_vrrp or _tree_get(self.vyos_running_tree, ["high-availability", "vrrp"])) else "",
            },
            "dhcp_leases": copy.deepcopy(self.dhcp_leases),
            "revisions": {
                "current": self.revision,
                "history_count": len(self.vyos_history),
                "commit_confirm_deadline": self.commit_confirm_deadline,
            },
            "uncommitted": uncommitted,
            "configure_mode": self.vyos_configure_mode,
            "edit_path": list(self.vyos_edit_path),
            "version": "VyOS 1.4-rolling-fixitlab",
            "diff": self.vyos_compare() if uncommitted else "",
        }

    def to_dict(self) -> dict:
        return {
            "scenario_slug": self.scenario_slug,
            "bgp_neighbors": self.bgp_neighbors,
            "ntp_synced": self.ntp_synced,
            "interface_mtu": self.interface_mtu,
            "vyos_running": self.vyos_running,
            "vyos_candidate": self.vyos_candidate,
            "vyos_configure_mode": self.vyos_configure_mode,
            "vyos_history": self.vyos_history,
            "vyos_running_tree": self.vyos_running_tree,
            "vyos_candidate_tree": self.vyos_candidate_tree,
            "vyos_edit_path": self.vyos_edit_path,
            "revision": self.revision,
            "commit_confirm_deadline": self.commit_confirm_deadline,
            "commit_confirm_seconds": self.commit_confirm_seconds,
            "vyos_firewall_rules": self.vyos_firewall_rules,
            "vyos_vrrp": self.vyos_vrrp,
            "vyos_nat": self.vyos_nat,
            "dhcp_leases": self.dhcp_leases,
            "firewall_counters": self.firewall_counters,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "NetworkingState":
        net = cls(data.get("scenario_slug") or "")
        net.bgp_neighbors = data.get("bgp_neighbors") or net.bgp_neighbors
        net.ntp_synced = data.get("ntp_synced", net.ntp_synced)
        net.interface_mtu = data.get("interface_mtu", net.interface_mtu)
        if data.get("vyos_running") is not None:
            net.vyos_running = data["vyos_running"]
        if data.get("vyos_candidate") is not None:
            net.vyos_candidate = data["vyos_candidate"]
        net.vyos_configure_mode = bool(data.get("vyos_configure_mode"))
        net.vyos_history = data.get("vyos_history") or net.vyos_history
        if data.get("vyos_running_tree"):
            net.vyos_running_tree = data["vyos_running_tree"]
        if data.get("vyos_candidate_tree"):
            net.vyos_candidate_tree = data["vyos_candidate_tree"]
        net.vyos_edit_path = list(data.get("vyos_edit_path") or [])
        net.revision = int(data.get("revision") or 0)
        net.commit_confirm_deadline = data.get("commit_confirm_deadline")
        net.commit_confirm_seconds = data.get("commit_confirm_seconds")
        net.vyos_firewall_rules = list(data.get("vyos_firewall_rules") or [])
        net.vyos_vrrp = bool(data.get("vyos_vrrp"))
        net.vyos_nat = bool(data.get("vyos_nat"))
        net.dhcp_leases = data.get("dhcp_leases") or net.dhcp_leases
        net.firewall_counters = data.get("firewall_counters") or {}
        net._sync_tree_alias()
        return net
