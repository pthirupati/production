"""Interactive RHEL boot sequence — GRUB, kernel, initramfs, login."""

from __future__ import annotations

import time
from dataclasses import dataclass, field


GRUB_MENU = """\
GNU GRUB  version 2.06

┌─────────────────────────────────────────────────────────────┐
│*Red Hat Enterprise Linux (5.14.0-362.el9.x86_64) 9.3       │
│ Red Hat Enterprise Linux (rescue mode) 9.3                 │
│ UEFI Firmware Settings                                       │
└─────────────────────────────────────────────────────────────┘
Use ↑↓ to select, 'e' to edit, 'c' for command-line, Enter to boot.
"""

KERNEL_BOOT_OK = """\
[    0.000000] Linux version 5.14.0-362.el9.x86_64 (mockbuild@redhat) #1 SMP
[    0.312441] systemd[1]: systemd 252-13.el9 running in system mode (+PAM +AUDIT)
[    1.102331] systemd[1]: Reached target Basic System.
[    2.441002] systemd[1]: Started FixitLab simulated RHEL 9.3.
[    3.001882] systemd[1]: Reached target Multi-User System.
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
error: file `/vmlinuz-5.14.0-362.el9.x86_64' not found.
error: you need to load the kernel first.
Entering rescue mode...
grub rescue> _
"""

MBR_CORRUPT = """\
GRUB Loading stage1.5.
GRUB loading, please wait...
Error 15: File not found
"""

PATCHING_OUTPUT = """\
Updating Subscription Management repositories.
Last metadata expiration check: 0:00:01 ago on Fri 14 Jun 2026 10:00:00 AM UTC.
Dependencies resolved.
================================================================================
 Package                    Arch   Version           Repository           Size
================================================================================
Installing:
 kernel                     x86_64 5.14.0-427.el9    rhel-9-base         712 k
Upgrading:
 glibc                      x86_64 2.34-125.el9      rhel-9-base         2.1 M
 systemd                    x86_64 252-46.el9        rhel-9-base         4.2 M
Transaction Summary
================================================================================
Install  1 Package
Upgrade  2 Packages
Total download size: 7.0 M
Downloading Packages:
(1/3): kernel-5.14.0-427.el9.x86_64.rpm           100% |██████████| 712 kB
(2/3): glibc-2.34-125.el9.x86_64.rpm                100% |██████████| 2.1 MB
(3/3): systemd-252-46.el9.x86_64.rpm                100% |██████████| 4.2 MB
Running transaction check
Running transaction test
Transaction test succeeded.
Running transaction
  Installing : kernel-5.14.0-427.el9.x86_64                                 1/3
  Upgrading  : glibc-2.34-125.el9.x86_64                                      2/3
  Upgrading  : systemd-252-46.el9.x86_64                                    3/3
  Cleanup    : glibc-2.34-100.el9.x86_64
Complete!
*** Reboot recommended to load new kernel ***
"""


@dataclass
class BootState:
    """Tracks interactive boot progress."""

    issue: str = "none"  # none | initramfs | grub_missing | mbr | kernel_panic | grub_cfg
    phase: str = "grub"  # post | grub | booting | initramfs | panic | login | shell | patching
    logged_in: bool = False
    username: str = ""
    kernel: str = "5.14.0-362.el9.x86_64"
    grub_fixed: bool = False
    initramfs_fixed: bool = False
    mbr_fixed: bool = False
    kernel_fixed: bool = False
    patching_done: bool = False
    boot_count: int = 0
    grub_shown: bool = False
    linux_cmdline: str = "ro crashkernel=auto rhgb quiet"
    initrd_path: str = "/initramfs-5.14.0-362.el9.img"
    vmlinuz_path: str = "/vmlinuz-5.14.0-362.el9.x86_64"

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
        elif "kernel-panic" in s or "kernel" in s and "panic" in s:
            self.issue = "kernel_panic"
        elif "grub" in s:
            self.issue = "grub_cfg"
        elif "patch" in s or "dnf-update" in s or "yum-update" in s:
            self.issue = "patching"

    def reboot(self) -> str:
        self.boot_count += 1
        self.logged_in = False
        self.username = ""
        self.grub_shown = False
        if self.issue == "mbr" and not self.mbr_fixed:
            self.phase = "mbr"
            return MBR_CORRUPT
        if self.issue == "grub_missing" and not self.grub_fixed:
            self.phase = "grub_rescue"
            return GRUB_RESCUE.replace("\n", "\r\n")
        self.phase = "grub"
        return GRUB_MENU.replace("\n", "\r\n")

    def start_boot(self, single_user: bool = False) -> str:
        self.phase = "booting"
        if self.issue == "mbr" and not self.mbr_fixed:
            self.phase = "mbr"
            return MBR_CORRUPT
        if self.issue == "grub_missing" and not self.grub_fixed:
            self.phase = "grub_rescue"
            return GRUB_RESCUE.replace("\n", "\r\n")

        if self.issue == "initramfs" and not self.initramfs_fixed:
            self.phase = "initramfs"
            return INITRAMFS_DRACUT_FAIL.replace("\n", "\r\n")

        if self.issue == "kernel_panic" and not self.kernel_fixed:
            self.phase = "panic"
            return KERNEL_PANIC.replace("\n", "\r\n")

        out = KERNEL_BOOT_OK.replace("\n", "\r\n")
        if single_user:
            self.phase = "login"
            out += "\r\n*** Booting to single-user / maintenance mode ***\r\nGive root password for maintenance\r\n"
            return out
        self.phase = "login"
        out += "\r\n\r\nRHEL 9.3 FixitLab Simulated Server\r\nrhel-sim login: "
        return out

    def handle_grub(self, line: str) -> str:
        low = line.lower().strip()
        if low in ("", "boot", "1", "rhel", "red hat"):
            return self.start_boot()
        if "single" in low or "rescue" in low or low == "2":
            return self.start_boot(single_user=True)
        if low == "e":
            return (
                "Editing boot entry...\r\n"
                f"  linux   {self.vmlinuz_path} {self.linux_cmdline}\r\n"
                f"  initrd  {self.initrd_path}\r\n"
                "Press Ctrl+X to boot with this configuration."
            )
        if low == "c":
            return "grub> "
        return "Unknown GRUB command. Press Enter to boot default entry."

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
            return "GRUB installed. Reboot to continue."
        return f"grub rescue> unknown command (try: set root=(hd0,1); linux /vmlinuz; initrd /initramfs.img; boot)"

    def handle_login(self, line: str) -> str:
        if not self.username:
            self.username = line.strip() or "root"
            self.phase = "password_wait"
            return "Password: "
        return "Login incorrect"

    def complete_login(self) -> str:
        self.logged_in = True
        self.phase = "shell"
        return (
            "\r\nWelcome to FixitLab RHEL 9.3 Simulation\r\n"
            "Last login: Fri Jun 14 10:00:00 UTC 2026 on tty1"
        )

    def run_patch_command(self, line: str) -> str:
        low = line.strip().lower()
        if any(x in low for x in ("dnf update", "yum update", "dnf upgrade", "yum upgrade")):
            self.patching_done = True
            return PATCHING_OUTPUT.replace("\n", "\r\n")
        return ""

    def fix_command(self, line: str) -> str | None:
        """Return non-None if command fixes boot issue."""
        low = line.strip().lower()
        if "dracut -f" in low or "dracut --force" in low:
            self.initramfs_fixed = True
            return "dracut: Generating initramfs for kernel 5.14.0-362.el9.x86_64...\ndracut: initramfs generation complete"
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
