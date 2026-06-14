"""Persistent firewalld zone state."""

from __future__ import annotations

from copy import deepcopy


class FirewallState:
    def __init__(self) -> None:
        self.default_zone = "public"
        self.runtime = {
            "public": {"services": ["ssh", "dhcpv6-client", "http"], "ports": []},
            "internal": {"services": ["ssh"], "ports": []},
        }
        self.permanent = deepcopy(self.runtime)

    def list_all(self, permanent: bool = False) -> str:
        zones = self.permanent if permanent else self.runtime
        z = zones.get(self.default_zone, {})
        svc = " ".join(z.get("services", []))
        ports = " ".join(z.get("ports", []))
        return (
            f"public (active)\n"
            f"  target: default\n"
            f"  services: {svc}\n"
            f"  ports: {ports}\n"
            f"  forward: no\n"
        )

    def add_port(self, port: str, permanent: bool = False) -> str:
        target = self.permanent if permanent else self.runtime
        zone = target.setdefault(self.default_zone, {"services": [], "ports": []})
        if port not in zone["ports"]:
            zone["ports"].append(port)
        return "success"

    def add_service(self, service: str, permanent: bool = False) -> str:
        target = self.permanent if permanent else self.runtime
        zone = target.setdefault(self.default_zone, {"services": [], "ports": []})
        if service not in zone["services"]:
            zone["services"].append(service)
        return "success"

    def reload(self) -> str:
        self.runtime = deepcopy(self.permanent)
        return "success"

    def is_port_open(self, port: int) -> bool:
        z = self.runtime.get(self.default_zone, {})
        port_str = f"{port}/tcp"
        return port_str in z.get("ports", []) or "http" in z.get("services", []) and port == 80
