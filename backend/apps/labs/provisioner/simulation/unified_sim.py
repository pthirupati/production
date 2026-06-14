"""Single unified simulation engine — one RHEL OS, scenario-driven behavior."""

from __future__ import annotations

from .base_sim import BaseRHELSimulator
from .boot_sequence import GRUB_MENU, BootState
from .k8s_cluster import K8sCluster
from .rhel_shell import RHELShell
from .shell import SimulationStreamHolder
from .sim_types import boot_console_for, hostname_for_type, normalize_sim_type
from .simulation_modules import apply_simulation_context, register_modules


class UnifiedSimulationEngine(BaseRHELSimulator):
    """
    One simulation engine for all scenarios.
    simulation_type selects the technology persona; scenario slug sets the broken state.
    Full RHEL command set always available.
    """

    def __init__(self, scenario_slug: str = "", simulation_type: str = "generic"):
        self.scenario_slug = scenario_slug
        self.simulation_type = normalize_sim_type(simulation_type)
        hostname = hostname_for_type(self.simulation_type, scenario_slug)
        self.scenario_slug = scenario_slug
        self.hostname = hostname

        super().__init__(scenario_slug=scenario_slug, hostname=hostname)

        self.cluster: K8sCluster | None = None
        self._ssh_key_fixed = False
        self._container_running = False
        self._power_state = "on"
        self.boot: BootState | None = None

        apply_simulation_context(self)
        register_modules(self)

        if boot_console_for(scenario_slug, self.simulation_type):
            self.boot = BootState()
            self.boot.apply_issue(scenario_slug)

    def _register_extras(self) -> None:
        pass  # modules registered in __init__ via register_modules

    def _register_extras_on(self, shell: RHELShell) -> None:
        register_modules(self, shell)

    def create_stream(self) -> SimulationStreamHolder:
        if self.boot and not self.boot.logged_in:
            return self._create_boot_stream()
        return super().create_stream()

    def _create_boot_stream(self) -> SimulationStreamHolder:
        engine = self
        get_ed, save_ed, clear_ed = self._stream_callbacks()

        def handler(line: str) -> str:
            return engine._handle_boot(line)

        def dyn_prompt() -> str:
            if engine.boot and engine.boot.phase in ("shell",) and engine.boot.logged_in:
                return engine.shell.prompt
            if engine.boot and engine.boot.phase == "grub_rescue":
                return "grub rescue> "
            if engine.boot and engine.boot.phase == "grub":
                return "grub> "
            if engine.boot and engine.boot.phase == "login":
                return "rhel-sim login: "
            if engine.boot and engine.boot.phase == "password_wait":
                return ""
            return engine.shell.prompt

        holder = SimulationStreamHolder(
            handler,
            prompt="grub> ",
            dynamic_prompt=dyn_prompt,
            get_editor_state=get_ed,
            save_editor=save_ed,
            clear_editor=clear_ed,
        )
        if not engine.boot.grub_shown:
            from .boot_sequence import GRUB_RESCUE, MBR_CORRUPT
            if engine.boot.phase == "mbr":
                holder._emit(MBR_CORRUPT.replace("\n", "\r\n"))
            elif engine.boot.phase == "grub_rescue":
                holder._emit(GRUB_RESCUE.replace("\n", "\r\n"))
            else:
                holder._emit(GRUB_MENU.replace("\n", "\r\n"))
            engine.boot.grub_shown = True
        return holder

    def _handle_boot(self, line: str) -> str:
        if not self.boot:
            return self.shell.run(line)
        fix = self.boot.fix_command(line)
        if fix:
            return fix
        if self.boot.phase in ("shell",) and self.boot.logged_in:
            patch = self.boot.run_patch_command(line)
            if patch:
                return patch
            out = self.shell.run(line)
            if out == "__REBOOT__":
                return self.boot.reboot()
            if line.strip().lower() in ("reboot", "systemctl reboot", "init 6"):
                return self.boot.reboot()
            return out
        if self.boot.phase == "grub":
            return self.boot.handle_grub(line)
        if self.boot.phase == "grub_rescue":
            return self.boot.handle_grub_rescue(line)
        if self.boot.phase in ("booting", "initramfs", "panic", "mbr"):
            if self.boot.initramfs_fixed or self.boot.mbr_fixed or self.boot.kernel_fixed:
                return self.boot.start_boot()
            return "System halted — fix boot issue then reboot"
        if self.boot.phase == "login":
            return self.boot.handle_login(line)
        if self.boot.phase == "password_wait":
            self.boot.logged_in = True
            self.boot.phase = "shell"
            self.shell.state.set_prompt_user(self.boot.username or "root")
            return self.boot.complete_login()
        return ""
