"""Bare-metal / IPMI simulation on full RHEL OS."""

from __future__ import annotations

from .base_sim import BaseRHELSimulator
from .rhel_shell import RHELShell


class BaremetalSimulator(BaseRHELSimulator):
    def __init__(self, scenario_slug: str = "baremetal-ipmi-power"):
        super().__init__(scenario_slug=scenario_slug, hostname="bmc-host")
        self._power_state = "on"

    def _register_extras(self) -> None:
        sim = self

        def ipmi_handler(parts: list[str], line: str) -> str | None:
            low = line.strip().lower()
            if not low.startswith("ipmitool") and not low.startswith("dmidecode") and not low.startswith("lshw"):
                return None
            return sim._ipmi_command(line)

        self.shell.register_handler(ipmi_handler)

    def _register_extras_on(self, shell: RHELShell) -> None:
        self._register_extras()

    def _ipmi_command(self, line: str) -> str:
        low = line.strip().lower()
        if low.startswith("ipmitool power status"):
            return f"Chassis Power is {self._power_state}"
        if low.startswith("ipmitool power reset") or low.startswith("ipmitool power cycle"):
            return "Chassis Power Control: Reset"
        if low.startswith("ipmitool power off"):
            self._power_state = "off"
            return "Chassis Power Control: Down/Off"
        if low.startswith("ipmitool power on"):
            self._power_state = "on"
            return "Chassis Power Control: Up/On"
        if low.startswith("ipmitool sensor"):
            return "CPU Temp        | 42 degrees C      | ok\nFan 1           | 4200 RPM          | ok\nPS1 Status      | 0x0180            | ok"
        if low.startswith("ipmitool fru"):
            return "FRU Device Description : Builtin FRU Device\n Board Product         : ProLiant DL380 Gen10"
        if low.startswith("ipmitool sol activate"):
            return "SOL Session operational. Use ~~. to exit\n[SOL Session operational.  Use ~? for help]\nrhel-baremetal login: "
        if low.startswith("dmidecode"):
            return "Manufacturer: HPE\nProduct Name: ProLiant DL380 Gen10"
        if low.startswith("lshw"):
            return "Architecture: x86_64\nCPU(s): 32\nModel name: Intel(R) Xeon(R) Gold 6248R"
        return f"{line}: OK (bare-metal simulation)"
