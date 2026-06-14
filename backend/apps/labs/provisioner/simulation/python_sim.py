"""Python debugging simulation."""

from __future__ import annotations

from .base_sim import BaseRHELSimulator


class PythonSimulator(BaseRHELSimulator):
    def __init__(self, scenario_slug: str = "sim-python-syntax-error"):
        super().__init__(scenario_slug=scenario_slug, hostname="dev-server")
        self.state._mkdir("/home/dev")
        self.state._write_file(
            "/home/dev/app.py",
            "#!/usr/bin/env python3\nprint(\"hello\"\n",
        )
        self.state.set_prompt_user("root")
        self.state.cwd = "/home/dev"

    def _register_extras(self) -> None:
        pass
