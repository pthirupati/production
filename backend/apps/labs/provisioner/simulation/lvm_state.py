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
