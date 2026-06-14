"""RHEL boot / GRUB / login simulation with full OS shell after login."""

from __future__ import annotations

from .base_sim import BaseRHELSimulator
from .shell import SimulationStreamHolder

GRUB_MENU = """\
GNU GRUB  version 2.06

┌─────────────────────────────────────────────────────────────┐
│*Red Hat Enterprise Linux (5.14.0-362.el9.x86_64) 9.3       │
│ Red Hat Enterprise Linux (rescue mode) 9.3                 │
│ UEFI Firmware Settings                                       │
└─────────────────────────────────────────────────────────────┘
Use ↑↓ to select, 'e' to edit, 'c' for command-line, Enter to boot.
"""

BOOT_LOG = """\
[    0.000000] Linux version 5.14.0-362.el9.x86_64 (mockbuild@redhat) #1 SMP
[    0.312441] systemd[1]: systemd 252-13.el9 running in system mode (+PAM +AUDIT)
[    1.102331] systemd[1]: Reached target Basic System.
[    2.441002] systemd[1]: Started FixitLab simulated RHEL 9.3.
[    3.001882] systemd[1]: Reached target Multi-User System.
"""


class BootSimulator(BaseRHELSimulator):
    """Interactive boot sequence with GRUB, login, then full RHEL shell."""

    def __init__(self, scenario_slug: str = "rhel-boot-grub-rescue"):
        super().__init__(scenario_slug=scenario_slug, hostname="rhel-sim")
        self.phase = "grub"
        self.logged_in = False
        self.username = ""
        self.kernel = "5.14.0-362.el9.x86_64"
        self._grub_shown = False
        self._shell_holder: SimulationStreamHolder | None = None

    def create_stream(self) -> SimulationStreamHolder:
        state = self

        def handler(line: str) -> str:
            return state.handle(line)

        holder = SimulationStreamHolder(handler, prompt="grub> ")
        if not state._grub_shown:
            holder._emit(GRUB_MENU.replace("\n", "\r\n"))
            state._grub_shown = True
        return holder

    def handle(self, line: str) -> str:
        if self.phase in ("shell", "single") and self.logged_in:
            out = self.shell.run(line)
            if out == "__REBOOT__":
                self.phase = "grub"
                self.logged_in = False
                self.username = ""
                self._grub_shown = False
                return GRUB_MENU.replace("\n", "\r\n")
            return out

        low = line.lower().strip()

        if self.phase == "grub":
            if low in ("", "boot", "1", "rhel", "red hat"):
                return self._start_boot()
            if "single" in low or "rescue" in low or low == "2":
                self.kernel = "rescue"
                return self._start_boot(single_user=True)
            if low == "e":
                return (
                    "Editing boot entry...\r\n"
                    "  linux   /vmlinuz-5.14.0-362.el9.x86_64 ro crashkernel=auto\r\n"
                    "  initrd  /initramfs-5.14.0-362.el9.img\r\n"
                    "Press Ctrl+X to boot with this configuration."
                )
            if low == "c":
                return "grub> "
            return "Unknown GRUB command. Press Enter to boot default entry."

        if self.phase == "booting":
            return "(system still booting — wait for login prompt)"

        if self.phase == "login":
            if not self.username:
                self.username = line.strip() or "root"
                self.phase = "password_wait"
                return "Password: "
            return "Login incorrect"

        if self.phase == "password_wait":
            self.logged_in = True
            self.phase = "single" if self.kernel == "rescue" else "shell"
            self.shell.state.set_prompt_user(self.username or "root")
            return (
                f"\r\nWelcome to FixitLab RHEL 9.3 Simulation\r\n"
                f"Last login: Fri Jun 14 10:00:00 UTC 2026 on tty1"
            )

        return ""

    def _start_boot(self, single_user: bool = False) -> str:
        self.phase = "booting"
        out = BOOT_LOG.replace("\n", "\r\n")
        if single_user:
            self.phase = "login"
            out += "\r\n*** Booting to single-user / maintenance mode ***\r\n"
            out += "Give root password for maintenance\r\n"
            return out
        self.phase = "login"
        out += "\r\n\r\nRHEL 9.3 FixitLab Simulated Server\r\nrhel-sim login: "
        return out
