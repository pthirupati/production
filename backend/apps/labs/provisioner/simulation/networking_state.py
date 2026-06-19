"""In-memory networking state (BGP, NTP, MTU)."""

from __future__ import annotations


class NetworkingState:
    def __init__(self, scenario_slug: str = "") -> None:
        self.scenario_slug = scenario_slug.lower()
        self.bgp_neighbors = [
            {"neighbor": "10.0.0.2", "remote_as": 65001, "state": "Established", "prefixes": 142},
        ]
        self.ntp_synced = True
        self.interface_mtu = 1500
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
            return "Reference ID    : C0A80101 (ntp.fixitlab.local)\nStratum         : 2\nSystem time     : synced"
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
