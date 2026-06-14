"""MySQL / PostgreSQL simulation on RHEL."""

from __future__ import annotations

from .base_sim import BaseRHELSimulator
from .rhel_os import SimService
from .rhel_shell import RHELShell


class DatabaseSimulator(BaseRHELSimulator):
    def __init__(self, scenario_slug: str = "sim-mysql-wont-start"):
        super().__init__(scenario_slug=scenario_slug, hostname="db-server")
        self._apply_db_preset(scenario_slug)

    def _apply_db_preset(self, slug: str) -> None:
        s = slug.lower()
        if "postgres" in s:
            self.state.services["postgresql"] = SimService(
                "postgresql", active="failed", enabled="enabled", description="PostgreSQL database server",
            )
            self.state._mkdir("/var/lib/pgsql")
            self.state._write_file("/var/lib/pgsql/data/postgresql.conf", "port = 5432\nlisten_addresses = 'localhost'\n")
        else:
            self.state.services["mysqld"] = SimService(
                "mysqld", active="failed", enabled="enabled", description="MySQL Server",
            )
            self.state._mkdir("/var/lib/mysql")
            self.state._write_file("/etc/my.cnf", "[mysqld]\ndatadir=/var/lib/mysql\nsocket=/var/lib/mysql/mysql.sock\n")

    def _register_extras(self) -> None:
        sim = self

        def db_handler(parts: list[str], line: str) -> str | None:
            low = line.strip().lower()
            if low.startswith("mysqladmin"):
                if "ping" in low:
                    svc = sim.state.services.get("mysqld")
                    if svc and svc.active == "active":
                        return "mysqld is alive"
                    return "mysqladmin: connect to server at 'localhost' failed"
            return None

        self.shell.register_handler(db_handler)
