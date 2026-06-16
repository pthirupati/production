"""Single unified simulation engine — one RHEL OS, scenario-driven behavior."""

from __future__ import annotations

import threading
import time

from .base_sim import BaseRHELSimulator
from .boot_sequence import BootState
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
            if self.boot.start_at_shell:
                self.shell.state.patching_done = False
                self._sync_boot_to_state()

        self.shell._engine = self  # noqa: SLF001 — simulation shell needs reboot hook
        self._stream_holder: SimulationStreamHolder | None = None
        self._grub_countdown_token = 0

    def _register_extras(self) -> None:
        pass

    def _register_extras_on(self, shell: RHELShell) -> None:
        register_modules(self, shell)
        shell._engine = self  # noqa: SLF001

    def _sync_boot_to_state(self) -> None:
        """Keep BootState flags aligned with RHELOSState for validation."""
        if not self.boot:
            return
        st = self.shell.state
        st.patching_done = st.patching_done or self.boot.patching_done
        st.rebooted_after_patch = st.rebooted_after_patch or self.boot.rebooted_after_patch
        st.kernel = self.boot.kernel
        st.grub_fixed = st.grub_fixed or self.boot.grub_fixed
        st.initramfs_fixed = st.initramfs_fixed or self.boot.initramfs_fixed
        st.mbr_fixed = st.mbr_fixed or self.boot.mbr_fixed
        st.kernel_fixed = st.kernel_fixed or self.boot.kernel_fixed
        self.boot.patching_done = st.patching_done
        self.boot.rebooted_after_patch = st.rebooted_after_patch

    def create_stream(self) -> SimulationStreamHolder:
        if self.boot and not self.boot.logged_in and not self.boot.start_at_shell:
            return self._create_boot_stream()
        return self._create_shell_stream()

    def _create_shell_stream(self) -> SimulationStreamHolder:
        engine = self
        get_ed, save_ed, clear_ed = self._stream_callbacks()

        def handler(line: str) -> str:
            return engine._handle_shell(line)

        holder = SimulationStreamHolder(
            handler,
            prompt=engine.shell.prompt,
            dynamic_prompt=lambda: engine.shell.prompt,
            get_editor_state=get_ed,
            save_editor=save_ed,
            clear_editor=clear_ed,
        )
        engine._stream_holder = holder
        if engine.boot and engine.boot.start_at_shell and not getattr(engine, "_patch_hint_shown", False):
            engine._patch_hint_shown = True
            holder._emit(
                "\r\n\x1b[1;36m[FixitLab Patching Lab]\x1b[0m\r\n"
                "Run \x1b[1;33m/opt/fixitlab/precheck.sh\x1b[0m, apply updates with "
                "\x1b[1;33mdnf update -y\x1b[0m, \x1b[1;33mreboot\x1b[0m, then "
                "\x1b[1;33m/opt/fixitlab/postcheck.sh\x1b[0m.\r\n"
                "Login: \x1b[1;33mroot\x1b[0m / \x1b[1;33mredhat\x1b[0m\r\n"
            )
        return holder

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
            if engine.boot and engine.boot.phase == "grub_edit":
                return "grub edit> "
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
        engine._stream_holder = holder
        if engine.boot and not engine.boot.grub_shown:
            holder._emit(engine.boot.grub_banner())
            engine.boot.grub_shown = True
            engine._start_grub_countdown(holder)
        return holder

    def _start_grub_countdown(self, holder: SimulationStreamHolder) -> None:
        boot = self.boot
        if not boot or boot.phase != "grub":
            return
        self._grub_countdown_token += 1
        token = self._grub_countdown_token

        def run() -> None:
            for remaining in range(boot.grub_timeout, 0, -1):
                time.sleep(1)
                if token != self._grub_countdown_token or boot.phase != "grub" or boot.logged_in:
                    return
                if remaining > 1:
                    holder._emit(
                        f"\r\n\x1b[2m  >> auto-boot in {remaining - 1}s "
                        f"(Enter to boot now, 'e' to edit)\x1b[0m\r\ngrub> "
                    )
            if token != self._grub_countdown_token or boot.phase != "grub" or boot.logged_in:
                return
            out = boot.start_boot()
            if out:
                holder._emit(out if out.endswith("\r\n") else out + "\r\n")
            if boot.phase == "login":
                holder.set_prompt("rhel-sim login: ")

        threading.Thread(target=run, daemon=True).start()

    def _cancel_grub_countdown(self) -> None:
        self._grub_countdown_token += 1

    def _reboot_from_shell(self) -> str:
        if not self.boot:
            return "\r\n\x1b[1;33mSystem rebooting...\x1b[0m\r\n"
        self._sync_boot_to_state()
        if self.boot.issue == "patching" and not self.shell.state.patching_done:
            return (
                "\r\n\x1b[1;31mCannot reboot yet — apply patches first "
                "(dnf update -y).\x1b[0m\r\n"
            )
        if self.boot.issue == "patching" and self.shell.state.patching_done:
            self.shell.state.rebooted_after_patch = True
            self.boot.rebooted_after_patch = True
            from .boot_sequence import NEW_KERNEL
            self.boot.kernel = NEW_KERNEL
            self.shell.state.kernel = NEW_KERNEL
        self.shell.state.current_user = "root"
        self.shell.state.cwd = "/root"
        self.boot.logged_in = False
        self.boot.phase = "grub"
        out = self.boot.reboot()
        self.boot.grub_shown = True
        if self._stream_holder:
            self._start_grub_countdown(self._stream_holder)
        return f"\r\n\x1b[1;33mConnection to simulation host closed by remote host.\x1b[0m\r\n{out}"

    def _handle_shell(self, line: str) -> str:
        if self.boot and not self.boot.logged_in and self.boot.phase in (
            "grub", "grub_edit", "grub_rescue", "login", "password_wait", "mbr", "booting", "initramfs", "panic",
        ):
            return self._handle_boot(line)
        low = line.strip().lower()
        if low in ("reboot", "systemctl reboot", "init 6", "shutdown -r now", "shutdown -r now"):
            return self._reboot_from_shell()
        out = self.shell.run(line)
        if out == "__REBOOT__":
            return self._reboot_from_shell()
        if self.boot:
            patch = self.boot.run_patch_command(line)
            if patch:
                self.shell.state.patching_done = True
                self.boot.patching_done = True
                return patch
            self._sync_boot_to_state()
        return out

    def _handle_boot(self, line: str) -> str:
        if not self.boot:
            return self.shell.run(line)
        fix = self.boot.fix_command(line)
        if fix:
            self._sync_boot_to_state()
            return fix
        if self.boot.phase in ("shell",) and self.boot.logged_in:
            return self._handle_shell(line)
        if low := line.strip().lower():
            if low in ("reboot", "systemctl reboot", "init 6", "shutdown -r now"):
                return self._reboot_from_shell()
        if self.boot.phase == "grub":
            self._cancel_grub_countdown()
            return self.boot.handle_grub(line)
        if self.boot.phase == "grub_edit":
            self._cancel_grub_countdown()
            return self.boot.handle_grub_edit(line)
        if self.boot.phase == "grub_rescue":
            return self.boot.handle_grub_rescue(line)
        if self.boot.phase in ("booting", "initramfs", "panic", "mbr"):
            if self.boot.initramfs_fixed or self.boot.mbr_fixed or self.boot.kernel_fixed:
                return self.boot.start_boot()
            return "System halted — fix boot issue then reboot"
        if self.boot.phase == "login":
            return self.boot.handle_login(line)
        if self.boot.phase == "password_wait":
            if not self.boot.verify_password(line):
                self.boot.phase = "login"
                self.boot.username = ""
                return "\r\nLogin incorrect\r\nrhel-sim login: "
            self.boot.logged_in = True
            self.boot.phase = "shell"
            self.shell.state.set_prompt_user(self.boot.username or "root")
            self._sync_boot_to_state()
            return self.boot.complete_login()
        return ""
