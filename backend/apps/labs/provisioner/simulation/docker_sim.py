"""Docker troubleshooting simulation."""

from __future__ import annotations

from .base_sim import BaseRHELSimulator
from .rhel_os import SimService


class DockerSimulator(BaseRHELSimulator):
    def __init__(self, scenario_slug: str = "sim-docker-container-exited"):
        super().__init__(scenario_slug=scenario_slug, hostname="docker-host")
        self.state.services["docker"] = SimService(
            "docker", active="active", enabled="enabled", description="Docker Application Container Engine",
        )
        self._container_running = False

    def _register_extras(self) -> None:
        sim = self

        def docker_handler(parts: list[str], line: str) -> str | None:
            if not line.strip().lower().startswith("docker"):
                return None
            low = line.strip().lower()
            if "docker start" in low:
                sim._container_running = True
                return "web"
            if "docker ps" in low and "-a" not in low:
                if sim._container_running:
                    return "CONTAINER ID   IMAGE          STATUS         NAMES\nabc123         nginx:latest   Up 1 second    web"
                return "CONTAINER ID   IMAGE          STATUS                     NAMES\nabc123         nginx:latest   Exited (1) 2 hours ago     web"
            return None

        self.shell.register_handler(docker_handler)
