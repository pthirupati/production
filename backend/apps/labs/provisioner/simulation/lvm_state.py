"""Simulated LVM2 physical volumes, volume groups, logical volumes."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SimPV:
    device: str
    vg: str = ""
    size: str = "50.00g"
    free: str = "50.00g"


@dataclass
class SimVG:
    name: str
    size: str = "50.00g"
    free: str = "10.00g"
    pvs: list[str] = field(default_factory=list)


@dataclass
class SimLV:
    name: str
    vg: str
    size: str = "40.00g"
    mount: str = ""
    lv_path: str = ""


class LVMState:
    def __init__(self) -> None:
        self.pvs: dict[str, SimPV] = {
            "/dev/sda2": SimPV("/dev/sda2", "rhel", "48.00g", "0"),
            "/dev/sdb": SimPV("/dev/sdb", "", "50.00g", "50.00g"),
        }
        self.vgs: dict[str, SimVG] = {
            "rhel": SimVG("rhel", "48.00g", "8.00g", ["/dev/sda2"]),
        }
        self.lvs: dict[str, SimLV] = {
            "rhel/root": SimLV("root", "rhel", "40.00g", "/", "/dev/mapper/rhel-root"),
            "rhel/swap": SimLV("swap", "rhel", "8.00g", "[SWAP]", "/dev/mapper/rhel-swap"),
        }

    def provision_disk(self, device: str) -> None:
        """Attach a disk that was provisioned via Jira @storage team."""
        if device not in self.pvs:
            self.pvs[device] = SimPV(device, "", "50.00g", "50.00g")

    def pvcreate(self, device: str) -> tuple[bool, str]:
        if device not in self.pvs:
            self.pvs[device] = SimPV(device, "", "50.00g", "50.00g")
        elif self.pvs[device].vg:
            return False, f"  Can't initialize physical volume \"{device}\" of volume group \"{self.pvs[device].vg}\""
        return True, f"  Physical volume \"{device}\" successfully created."

    def vgextend(self, vg: str, pv: str) -> tuple[bool, str]:
        if vg not in self.vgs:
            return False, f"  Volume group \"{vg}\" not found"
        if pv not in self.pvs:
            return False, f"  Device {pv} not found"
        self.pvs[pv].vg = vg
        self.vgs[vg].pvs.append(pv)
        self.vgs[vg].free = "58.00g"
        self.vgs[vg].size = "98.00g"
        return True, f"  Volume group \"{vg}\" successfully extended"

    def lvcreate(self, name: str, vg: str, size: str) -> tuple[bool, str]:
        if vg not in self.vgs:
            return False, f"  Volume group \"{vg}\" not found"
        key = f"{vg}/{name}"
        if key in self.lvs:
            return False, f"  Logical Volume \"{name}\" already exists in volume group \"{vg}\"."
        size_norm = (size or "1g").lower().replace("g", ".00g") if "." not in (size or "") else size
        lv_path = f"/dev/mapper/{vg}-{name}"
        self.lvs[key] = SimLV(name, vg, size_norm, "", lv_path)
        # Reduce VG free space.
        free_kb = self._size_to_kb(self.vgs[vg].free)
        used_kb = self._size_to_kb(size_norm)
        new_free = max(0, free_kb - used_kb)
        self.vgs[vg].free = f"{new_free / (1024 * 1024):.2f}g"
        return True, f"  Logical volume \"{name}\" created."

    def lvextend(self, lv_path: str, size: str) -> tuple[bool, str]:
        key = lv_path.replace("/dev/mapper/", "").replace("/", "/")
        if key not in self.lvs and lv_path not in self.lvs:
            for k, lv in self.lvs.items():
                if lv.lv_path == lv_path or k.endswith(lv_path.split("/")[-1]):
                    key = k
                    break
        lv = self.lvs.get(key)
        if not lv:
            return False, f"  Logical volume {lv_path} not found"
        if size and size.startswith("+"):
            old_kb = self._size_to_kb(lv.size)
            add_kb = self._size_to_kb(size[1:])
            new_kb = old_kb + add_kb
            lv.size = f"{new_kb // (1024 * 1024)}.00g"
        elif size:
            lv.size = size.replace("+", "").replace("L", "g") if size else "50.00g"
        return True, f"  Logical volume {lv.lv_path} successfully resized."

    def format_pvs(self) -> str:
        lines = ["  PV         VG   Fmt  Attr PSize   PFree"]
        for pv in self.pvs.values():
            lines.append(f"  {pv.device:<10} {pv.vg or '---':<4} lvm2 --- {pv.size:>6} {pv.free:>6}")
        return "\n".join(lines)

    def format_vgs(self) -> str:
        lines = ["  VG   #PV #LV #SN Attr   VSize  VFree"]
        for vg in self.vgs.values():
            lines.append(f"  {vg.name:<4} {len(vg.pvs):>2} {sum(1 for l in self.lvs.values() if l.vg == vg.name):>2}   0 wz--n- {vg.size:>5} {vg.free:>5}")
        return "\n".join(lines)

    def format_lvs(self) -> str:
        lines = ["  LV   VG   Attr       LSize  Pool Origin Data%  Meta%  Move Log Cpy%Sync Convert"]
        for key, lv in self.lvs.items():
            lines.append(f"  {lv.name:<4} {lv.vg:<4} -wi-ao---- {lv.size:>5}                                                     ")
        return "\n".join(lines)

    def format_df(self) -> str:
        lines = ["Filesystem                        1K-blocks    Used Available Use% Mounted on"]
        seen = set()
        for lv in self.lvs.values():
            if not lv.mount or lv.mount == "[SWAP]":
                continue
            path = lv.lv_path or f"/dev/mapper/{lv.vg}-{lv.name}"
            size_k = self._size_to_kb(lv.size)
            used = int(size_k * 0.17)
            avail = size_k - used
            lines.append(
                f"{path:<32} {size_k:>10} {used:>8} {avail:>10}  17% {lv.mount}"
            )
            seen.add(lv.mount)
        if "/" not in seen:
            lines.append("/dev/mapper/rhel-root              52428800 8388608  44040192  17% /")
        lines.append("tmpfs                              4026532       0   4026532   0% /dev/shm")
        return "\n".join(lines)

    def format_mount(self) -> str:
        lines = []
        for lv in self.lvs.values():
            if lv.mount and lv.mount != "[SWAP]":
                path = lv.lv_path or f"/dev/mapper/{lv.vg}-{lv.name}"
                lines.append(f"{path} on {lv.mount} type xfs (rw,relatime)")
        if not lines:
            lines.append("/dev/mapper/rhel-root on / type xfs (rw,relatime)")
        lines.append("/dev/sda2 on /boot type xfs (rw,relatime)")
        return "\n".join(lines)

    def format_fdisk(self) -> str:
        lines = [
            "Disk /dev/sda: 50 GiB",
            "Device     Boot   Start      End  Sectors  Size Id Type",
            "/dev/sda1  *       2048 104857566 104855519   50G 83 Linux",
        ]
        for dev, pv in self.pvs.items():
            if dev.startswith("/dev/sd") and dev not in ("/dev/sda1", "/dev/sda2"):
                lines.append(f"{dev:<10}        2048 104857566 104855519   50G 83 Linux")
        return "\n".join(lines)

    @staticmethod
    def _size_to_kb(size: str) -> int:
        s = (size or "40g").lower().replace(" ", "")
        if s.endswith("g"):
            return int(float(s[:-1]) * 1024 * 1024)
        if s.endswith("m"):
            return int(float(s[:-1]) * 1024)
        return 52428800
