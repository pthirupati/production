"""RHEL boot / GRUB / login simulation with full OS shell after login."""

from __future__ import annotations

from .base_sim import BaseRHELSimulator
from .boot_sequence import GRUB_MENU, BootState
from .shell import SimulationStreamHolder


class BootSimulator(BaseRHELSimulator):
    """Interactive boot sequence with GRUB, initramfs, MBR, kernel, patching."""

    def __init__(self, scenario_slug: str = "rhel-boot-grub-rescue"):
        super().__init__(scenario_slug=scenario_slug, hostname="rhel-sim")
        self.boot = BootState()
        self.boot.apply_issue(scenario_slug)

    def _stream_callbacks(self, shell=None):
        return super()._stream_callbacks(shell or self.shell)

    def create_stream(self) -> SimulationStreamHolder:
        state = self
        get_ed, save_ed, clear_ed = self._stream_callbacks()

        def handler(line: str) -> str:
            return state.handle(line)

        def dyn_prompt() -> str:
            if state.boot.phase in ("shell",) and state.boot.logged_in:
                return state.shell.prompt
            if state.boot.phase == "grub_rescue":
                return "grub rescue> "
            if state.boot.phase == "grub":
                return "grub> "
            if state.boot.phase == "login":
                return "rhel-sim login: "
            if state.boot.phase == "password_wait":
                return ""
            if state.boot.phase in ("initramfs", "panic", "mbr", "booting"):
                return "(boot)> "
            return state.shell.prompt

        holder = SimulationStreamHolder(
            handler,
            prompt="grub> ",
            dynamic_prompt=dyn_prompt,
            get_editor_state=get_ed,
            save_editor=save_ed,
            clear_editor=clear_ed,
        )
        if not state.boot.grub_shown:
            if state.boot.phase == "mbr":
                from .boot_sequence import MBR_CORRUPT
                holder._emit(MBR_CORRUPT.replace("\n", "\r\n"))
            elif state.boot.phase == "grub_rescue":
                from .boot_sequence import GRUB_RESCUE
                holder._emit(GRUB_RESCUE.replace("\n", "\r\n"))
            else:
                holder._emit(GRUB_MENU.replace("\n", "\r\n"))
            state.boot.grub_shown = True
        return holder

    def handle(self, line: str) -> str:
        fix_out = self.boot.fix_command(line)
        if fix_out:
            return fix_out

        if self.boot.phase in ("shell",) and self.boot.logged_in:
            patch_out = self.boot.run_patch_command(line)
            if patch_out:
                return patch_out
            out = self.shell.run(line)
            if out == "__REBOOT__":
                return self.boot.reboot()
            # Also intercept reboot variants
            low = line.strip().lower()
            if low in ("reboot", "shutdown -r now", "systemctl reboot", "init 6"):
                return self.boot.reboot()
            return out

        low = line.lower().strip()

        if self.boot.phase == "grub":
            return self.boot.handle_grub(line)

        if self.boot.phase == "grub_rescue":
            return self.boot.handle_grub_rescue(line)

        if self.boot.phase in ("booting", "initramfs", "panic", "mbr"):
            if self.boot.initramfs_fixed or self.boot.kernel_fixed or self.boot.mbr_fixed:
                return self.boot.start_boot()
            return "System halted — fix boot issue (dracut, grub2-install, etc.) then reboot"

        if self.boot.phase == "login":
            return self.boot.handle_login(line)

        if self.boot.phase == "password_wait":
            self.boot.logged_in = True
            self.boot.phase = "shell"
            self.shell.state.set_prompt_user(self.boot.username or "root")
            return self.boot.complete_login()

        return ""
