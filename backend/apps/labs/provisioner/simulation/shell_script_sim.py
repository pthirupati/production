"""Shell scripting simulation."""

from __future__ import annotations

from .base_sim import BaseRHELSimulator


class ShellScriptSimulator(BaseRHELSimulator):
    def __init__(self, scenario_slug: str = "sim-bash-script-broken"):
        super().__init__(scenario_slug=scenario_slug, hostname="script-host")
        self.state._mkdir("/opt/scripts")
        self.state._write_file(
            "/opt/scripts/backup.sh",
            "#!/bin/bash\nBACKUP_DIR=/var/backups\nif [ $DAY = Monday ]; then\n  tar -czf $BACKUP_DIR/full.tar.gz /data\nfi\n",
        )
        self.state._write_file("/opt/scripts/run.sh", "#!/bin/bash\nbash /opt/scripts/backup.sh\n")
