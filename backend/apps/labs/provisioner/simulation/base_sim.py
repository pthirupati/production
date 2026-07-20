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

    def _stream_callbacks(self, shell: RHELShell | None = None):
        sh = shell or self.shell

        def get_editor():
            return sh.state.editor

        def save_editor(path: str, content: str) -> None:
            sh.state.write_file(path, content)
            sh.state.editor = None

        def clear_editor() -> None:
            sh.state.editor = None

        return get_editor, save_editor, clear_editor

    def create_stream(self) -> SimulationStreamHolder:
        from .sim_types import lab_server_banner

        get_ed, save_ed, clear_ed = self._stream_callbacks()
        return SimulationStreamHolder(
            self.shell.run,
            prompt=self.shell.prompt,
            dynamic_prompt=lambda: self.shell.prompt,
            get_editor_state=get_ed,
            save_editor=save_ed,
            clear_editor=clear_ed,
            banner=lab_server_banner("generic", self.scenario_slug),
        )

    def create_stream_for_state(self, state: RHELOSState) -> SimulationStreamHolder:
        from .sim_types import lab_server_banner

        shell = RHELShell(state=state, scenario_slug=state.scenario_slug, hostname=state.hostname)
        self._register_extras_on(shell)
        get_ed, save_ed, clear_ed = self._stream_callbacks(shell)
        return SimulationStreamHolder(
            shell.run,
            prompt=shell.prompt,
            dynamic_prompt=lambda: shell.prompt,
            get_editor_state=get_ed,
            save_editor=save_ed,
            clear_editor=clear_ed,
            banner=lab_server_banner("generic", state.scenario_slug or self.scenario_slug),
        )

    def _register_extras_on(self, shell: RHELShell) -> None:
        """Re-attach extra handlers to another shell instance."""
        pass

    @property
    def state(self) -> RHELOSState:
        return self.shell.state


SimulationStreamHandler = SimulationStreamHolder
