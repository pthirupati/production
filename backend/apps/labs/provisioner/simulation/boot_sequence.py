"""Interactive RHEL boot sequence — GRUB, kernel, initramfs, login, patching."""

from __future__ import annotations

from dataclasses import dataclass, field


OLD_KERNEL = "5.14.0-362.el9.x86_64"
NEW_KERNEL = "5.14.0-427.el9.x86_64"
DEFAULT_PASSWORD = "redhat"


GRUB_MENU = """\
GNU GRUB  version 2.06

┌─────────────────────────────────────────────────────────────┐
│*{default_entry}│
│ {rescue_entry}                                               │
│ UEFI Firmware Settings                                       │
└─────────────────────────────────────────────────────────────┘
Use ↑↓ to select, 'e' to edit, 'c' for command-line, Enter to boot.
The highlighted entry will be executed automatically in {timeout}s.
"""

KERNEL_BOOT_OK = """\
[    0.000000] Linux version {kernel} (mockbuild@redhat) #1 SMP
[    0.312441] e820: BIOS-provided physical RAM map
[    0.881102] systemd[1]: systemd 252-46.el9 running in system mode (+PAM +AUDIT)
[    1.441002] systemd[1]: Started systemd-journald.service
[    2.102331] systemd[1]: Reached target Swap.
[    2.881102] systemd[1]: Starting dracut initqueue hook...
[    3.441002] systemd[1]: Mounting /sysroot...
[    4.102331] systemd[1]: Mounted /sysroot.
[    4.881102] systemd[1]: Started NetworkManager.service
[    5.441002] systemd[1]: Reached target Network.
[    6.001882] systemd[1]: Started FixitLab RHEL 9.3 lab host.
[    6.441002] systemd[1]: Reached target Multi-User System.
"""

INITRAMFS_DRACUT_FAIL = """\
[    2.881102] dracut-initqueue[412]: Warning: dracut-initqueue timeout - starting timeout scripts
[    2.991331] dracut-initqueue[412]: Warning: Could not boot.
[    3.001002] dracut-initqueue[412]: Warning: /dev/mapper/rhel-root does not exist
*** Gave up waiting for root device. Common fixes:
*** - Regenerate initramfs: dracut -f
*** - Check /etc/fstab UUIDs
*** - Boot rescue entry and chroot
"""

KERNEL_PANIC = """\
[    1.441002] Kernel panic - not syncing: VFS: Unable to mount root fs on unknown-block(0,0)
[    1.441102] ---[ end Kernel panic - not syncing ]---
"""

GRUB_RESCUE = """\
error: file `/vmlinuz-{kernel}' not found.
error: you need to load the kernel first.
Entering rescue mode...
grub rescue> _
"""

MBR_CORRUPT = """\
GRUB Loading stage1.5.
GRUB loading, please wait...
Error 15: File not found
"""

EMERGENCY_BOOT = """\
[    4.881102] systemd[1]: Cannot open access to console, the root account is locked.
[    4.991331] systemd[1]: Emergency mode started.
Give root password for maintenance
(or press Control-D to continue boot):
"""

EMERGENCY_SHELL = """\
\r\n\x1b[1;33m*** Emergency mode ***\x1b[0m\r\n
The system is in emergency mode due to a filesystem or fstab issue.
Logs: journalctl -xb | less
Fix /etc/fstab or run dracut -f, then \x1b[1;33mreboot\x1b[0m.
Suggested: cat /etc/fstab — verify UUIDs match blkid output.
"""

PATCHING_OUTPUT = """\
Updating Subscription Management repositories.
Last metadata expiration check: 0:00:01 ago on Fri 14 Jun 2026 10:00:00 AM UTC.
Dependencies resolved.
================================================================================
 Package                    Arch   Version           Repository           Size
================================================================================
Installing:
 kernel                     x86_64 {new_kernel}    rhel-9-base         712 k
Upgrading:
 glibc                      x86_64 2.34-125.el9      rhel-9-base         2.1 M
 systemd                    x86_64 252-46.el9        rhel-9-base         4.2 M
Transaction Summary
================================================================================
Install  1 Package
Upgrade  2 Packages
Total download size: 7.0 M
Downloading Packages:
(1/3): kernel-{new_kernel}.rpm                      100% |██████████| 712 kB
(2/3): glibc-2.34-125.el9.x86_64.rpm                100% |██████████| 2.1 MB
(3/3): systemd-252-46.el9.x86_64.rpm                100% |██████████| 4.2 MB
Running transaction check
Running transaction test
Transaction test succeeded.
Running transaction
  Installing : kernel-{new_kernel}                                 1/3
  Upgrading  : glibc-2.34-125.el9.x86_64                              2/3
  Upgrading  : systemd-252-46.el9.x86_64                                    3/3
  Cleanup    : glibc-2.34-100.el9.x86_64
  Cleanup    : kernel-{old_kernel}
Complete!
*** Reboot required to load new kernel {new_kernel} ***
"""


def _grub_menu(kernel: str, timeout: int = 5) -> str:
    default = f"Red Hat Enterprise Linux ({kernel}) 9.3"
    rescue = "Red Hat Enterprise Linux (rescue mode) 9.3"
    return GRUB_MENU.format(default_entry=default, rescue_entry=rescue, timeout=timeout)


@dataclass
class BootState:
    """Tracks interactive boot progress."""

    issue: str = "none"
    phase: str = "grub"
    logged_in: bool = False
    start_at_shell: bool = False
    username: str = ""
    kernel: str = OLD_KERNEL
    grub_fixed: bool = False
    initramfs_fixed: bool = False
    mbr_fixed: bool = False
    kernel_fixed: bool = False
    patching_done: bool = False
    rebooted_after_patch: bool = False
    boot_count: int = 0
    grub_shown: bool = False
    grub_timeout: int = 5
    grub_editing: bool = False
    linux_cmdline: str = "ro crashkernel=auto rhgb quiet"
    initrd_path: str = f"/initramfs-{OLD_KERNEL}.img"
    vmlinuz_path: str = f"/vmlinuz-{OLD_KERNEL}"
    password_hint_shown: bool = False

    def apply_issue(self, slug: str) -> None:
        s = slug.lower()
        if "initramfs" in s or "dracut" in s:
            self.issue = "initramfs"
        elif "grub-rescue" in s or "grub-rebuild" in s or "grub-missing" in s:
            self.issue = "grub_missing"
            self.phase = "grub_rescue"
        elif "mbr" in s:
            self.issue = "mbr"
            self.phase = "mbr"
        elif "kernel-panic" in s or ("kernel" in s and "panic" in s):
            self.issue = "kernel_panic"
        elif "grub" in s or "boot" in s:
            self.issue = "grub_cfg"
        elif "patch" in s or "dnf-update" in s or "yum-update" in s:
            self.issue = "patching"
            self.start_at_shell = True
            self.logged_in = True
            self.phase = "shell"
        elif "fstab" in s or "emergency" in s:
            self.issue = "fstab"

    def sync_kernel_paths(self) -> None:
        self.initrd_path = f"/initramfs-{self.kernel}.img"
        self.vmlinuz_path = f"/vmlinuz-{self.kernel}"

    def grub_banner(self) -> str:
        self.sync_kernel_paths()
        if self.issue == "mbr" and not self.mbr_fixed:
            return MBR_CORRUPT.replace("\n", "\r\n")
        if self.issue == "grub_missing" and not self.grub_fixed:
            return GRUB_RESCUE.format(kernel=self.kernel).replace("\n", "\r\n")
        return _grub_menu(self.kernel, self.grub_timeout).replace("\n", "\r\n")

    def reboot(self) -> str:
        self.boot_count += 1
        self.logged_in = False
        self.username = ""
        self.grub_shown = False
        self.password_hint_shown = False
        if self.issue == "patching" and self.patching_done:
            self.kernel = NEW_KERNEL
            self.rebooted_after_patch = True
            self.sync_kernel_paths()
        if self.issue == "mbr" and not self.mbr_fixed:
            self.phase = "mbr"
            return MBR_CORRUPT.replace("\n", "\r\n")
        if self.issue == "grub_missing" and not self.grub_fixed:
            self.phase = "grub_rescue"
            return GRUB_RESCUE.format(kernel=OLD_KERNEL).replace("\n", "\r\n")
        self.phase = "grub"
        return self.grub_banner()

    def start_boot(self, single_user: bool = False) -> str:
        self.phase = "booting"
        if self.issue == "mbr" and not self.mbr_fixed:
            self.phase = "mbr"
            return MBR_CORRUPT.replace("\n", "\r\n")
        if self.issue == "grub_missing" and not self.grub_fixed:
            self.phase = "grub_rescue"
            return GRUB_RESCUE.format(kernel=self.kernel).replace("\n", "\r\n")

        if self.issue == "initramfs" and not self.initramfs_fixed:
            self.phase = "initramfs"
            return INITRAMFS_DRACUT_FAIL.replace("\n", "\r\n")

        if self.issue == "fstab" and not self.initramfs_fixed:
            self.phase = "emergency"
            out = KERNEL_BOOT_OK.format(kernel=self.kernel).replace("\n", "\r\n")
            out += EMERGENCY_BOOT.replace("\n", "\r\n")
            return out

        if self.issue == "kernel_panic" and not self.kernel_fixed:
            self.phase = "panic"
            return KERNEL_PANIC.replace("\n", "\r\n")

        out = KERNEL_BOOT_OK.format(kernel=self.kernel).replace("\n", "\r\n")
        if single_user:
            self.phase = "login"
            out += "\r\n*** Booting to single-user / maintenance mode ***\r\nGive root password for maintenance\r\n"
            return out
        self.phase = "login"
        hint = ""
        if not self.password_hint_shown:
            self.password_hint_shown = True
            hint = "\r\n\x1b[1;33mHint: login as root, password redhat\x1b[0m\r\n"
        out += f"\r\n\r\nRHEL 9.3 FixitLab Lab Server\r\n{hint}rhel-lab login: "
        return out

    def handle_grub(self, line: str) -> str:
        low = line.lower().strip()
        if low in ("", "boot", "1", "rhel", "red hat"):
            return self.start_boot()
        if "single" in low or "rescue" in low or low == "2":
            return self.start_boot(single_user=True)
        if low == "e":
            self.grub_editing = True
            self.phase = "grub_edit"
            self.sync_kernel_paths()
            return (
                "Editing boot entry...\r\n"
                f"  linux   {self.vmlinuz_path} {self.linux_cmdline}\r\n"
                f"  initrd  {self.initrd_path}\r\n"
                "Edit lines (linux/initrd), then type 'boot' or Ctrl+X to boot."
            )
        if low == "c":
            return "grub> "
        if low.isdigit() and int(low) == self.grub_timeout:
            return self.start_boot()
        return "Unknown GRUB command. Press Enter to boot default entry (auto-boot in 5s)."

    def handle_grub_edit(self, line: str) -> str:
        low = line.strip().lower()
        if low in ("boot", "ctrl+x", "ctrl+x\r", "^x"):
            self.grub_editing = False
            self.phase = "grub"
            return self.start_boot()
        if low.startswith("linux ") or low.startswith("linux16 "):
            rest = line.strip().split(None, 1)
            payload = rest[1] if len(rest) > 1 else ""
            if payload:
                if " " in payload:
                    path, cmdline = payload.split(None, 1)
                    self.vmlinuz_path = path
                    self.linux_cmdline = cmdline
                else:
                    self.vmlinuz_path = payload
            return (
                f"  linux   {self.vmlinuz_path} {self.linux_cmdline}\r\n"
                f"  initrd  {self.initrd_path}\r\n"
            )
        if low.startswith("initrd ") or low.startswith("initrd16 "):
            self.initrd_path = line.strip().split(None, 1)[1]
            return f"  initrd  {self.initrd_path}\r\n"
        if low == "e":
            self.sync_kernel_paths()
            return (
                f"  linux   {self.vmlinuz_path} {self.linux_cmdline}\r\n"
                f"  initrd  {self.initrd_path}\r\n"
            )
        return "grub edit> unknown (edit linux/initrd lines, then type boot)"

    def handle_grub_rescue(self, line: str) -> str:
        low = line.strip().lower()
        if low.startswith("set root="):
            return ""
        if low.startswith("linux ") or low.startswith("linux16 "):
            self.grub_fixed = True
            return "kernel loaded"
        if low.startswith("initrd ") or low.startswith("initrd16 "):
            return "initrd loaded"
        if low == "boot":
            return self.start_boot()
        if "grub2-install" in low or "grub2-mkconfig" in low:
            self.grub_fixed = True
            return "GRUB installed. Type `reboot` to continue."
        return "grub rescue> unknown command (try: set root=(hd0,1); linux /vmlinuz; initrd /initramfs.img; boot)"

    def handle_login(self, line: str) -> str:
        if not self.username:
            self.username = line.strip() or "root"
            self.phase = "password_wait"
            return "Password: "
        return "Login incorrect"

    def verify_password(self, password: str) -> bool:
        user = (self.username or "root").strip()
        if user == "root":
            return password.strip() == DEFAULT_PASSWORD
        return bool(password.strip())

    def complete_emergency_login(self) -> str:
        self.logged_in = True
        self.phase = "emergency_shell"
        return EMERGENCY_SHELL

    def complete_login(self) -> str:
        self.logged_in = True
        self.phase = "shell"
        return (
            "\r\nWelcome to FixitLab RHEL 9.3 Lab Server\r\n"
            "Last login: Fri Jun 14 10:00:00 UTC 2026 on tty1"
        )

    def run_patch_command(self, line: str) -> str:
        low = line.strip().lower()
        if any(x in low for x in ("dnf update", "yum update", "dnf upgrade", "yum upgrade")):
            self.patching_done = True
            return PATCHING_OUTPUT.format(
                old_kernel=OLD_KERNEL,
                new_kernel=NEW_KERNEL,
            ).replace("\n", "\r\n")
        return ""

    def fix_command(self, line: str) -> str | None:
        """Return non-None if command fixes boot issue."""
        low = line.strip().lower()
        if "dracut -f" in low or "dracut --force" in low:
            self.initramfs_fixed = True
            return (
                f"dracut: Generating initramfs for kernel {self.kernel}...\r\n"
                "dracut: initramfs generation complete"
            )
        if "fstab" in low and ("uuid=" in low or "/ " in low):
            self.initramfs_fixed = True
            return "fstab entry updated (simulated)"
        if "grub2-mkconfig" in low:
            self.grub_fixed = True
            return "Generating grub configuration file ... done"
        if "grub2-install" in low:
            self.mbr_fixed = True
            self.grub_fixed = True
            return "Installation finished. No error reported."
        if "grub-install" in low:
            self.mbr_fixed = True
            return "Installation finished. No error reported."
        if "mkinitrd" in low or "new-kernel-pkg" in low:
            self.kernel_fixed = True
            self.initramfs_fixed = True
            return "initramfs rebuilt successfully"
        if "mount /sysroot" in low or "chroot /sysroot" in low:
            return "(rescue chroot simulated — run dracut -f or fix fstab)"
        return None
