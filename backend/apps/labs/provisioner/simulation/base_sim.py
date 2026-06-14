"""Base simulator wrapping full RHEL shell."""

from __future__ import annotations

from .rhel_os import RHELOSState
from .rhel_shell import RHELShell
from .shell import SimulationStreamHolder


class BaseRHELSimulator:
    """Full RHEL OS simulation — used directly or extended by specialized labs."""

    def __init__(self, scenario_slug: str = "", hostname: str = "rhel-sim"):
        self.scenario_slug = scenario_slug
        self.hostname = hostname
        self.shell = RHELShell(
            state=RHELOSState(hostname=hostname, scenario_slug=scenario_slug),
            scenario_slug=scenario_slug,
            hostname=hostname,
        )
        self._register_extras()

    def _register_extras(self) -> None:
        """Override to add scenario-specific command handlers."""
        pass

    def create_stream(self) -> SimulationStreamHandler:
        return SimulationStreamHolder(
            self.shell.run,
            prompt=self.shell.prompt,
        )

    def create_stream_for_state(self, state: RHELOSState) -> SimulationStreamHolder:
        shell = RHELShell(state=state, scenario_slug=state.scenario_slug, hostname=state.hostname)
        self._register_extras_on(shell)
        return SimulationStreamHolder(shell.run, prompt=shell.prompt)

    def _register_extras_on(self, shell: RHELShell) -> None:
        """Re-attach extra handlers to another shell instance."""
        pass

    @property
    def state(self) -> RHELOSState:
        return self.shell.state


# Typo fix alias for type hints
SimulationStreamHandler = SimulationStreamHolder
