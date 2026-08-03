"""In-memory networking state (BGP, NTP, MTU) + VyOS candidate/running config."""

from __future__ import annotations

import copy
import re


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
        self._apply_scenario()

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
            lines.append(
                f"{n['neighbor']:<15} 4 {n['remote_as']:<5} {n['state']:<11} {n['prefixes']}"
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

    # ── VyOS commit / rollback ─────────────────────────────────────────────
    def vyos_enter_configure(self) -> str:
        self.vyos_configure_mode = True
        self.vyos_candidate = self.vyos_running
        return "[edit]"

    def vyos_exit_configure(self) -> str:
        self.vyos_configure_mode = False
        self.vyos_candidate = self.vyos_running
        return "exit"

    def vyos_set(self, path: str) -> str:
        if not self.vyos_configure_mode:
            return "Error: configuration path is not open — run 'configure' first"
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
                        "remote_as": int(asn.group(1)) if asn else 65001,
                        "state": "Idle",
                        "prefixes": 0,
                    })
        return ""

    def vyos_delete(self, path: str) -> str:
        if not self.vyos_configure_mode:
            return "Error: configuration path is not open — run 'configure' first"
        path = (path or "").strip()
        marker = f"    # set {path}\n"
        self.vyos_candidate = self.vyos_candidate.replace(marker, "")
        return ""

    def vyos_commit(self) -> str:
        if not self.vyos_configure_mode:
            return "Error: configuration path is not open — run 'configure' first"
        if self.vyos_candidate == self.vyos_running:
            return "No configuration changes to commit"
        self.vyos_history.append(self.vyos_running)
        if len(self.vyos_history) > 10:
            self.vyos_history = self.vyos_history[-10:]
        self.vyos_running = self.vyos_candidate
        for n in self.bgp_neighbors:
            if n.get("state") == "Idle":
                n["state"] = "Established"
                n["prefixes"] = max(n.get("prefixes") or 0, 42)
        return "[edit]\nCommit complete."

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
        return f"[edit]\nRollback complete — restored revision -{steps}."

    def vyos_show_config(self, *, candidate: bool = False) -> str:
        return self.vyos_candidate if candidate else self.vyos_running
