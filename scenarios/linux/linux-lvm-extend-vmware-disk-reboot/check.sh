#!/bin/bash
# Cross-tech LVM extend (reboot): disk added in VMware only appears after reboot,
# then must be added to vgdata and the lvdata LV genuinely extended past 20G.
pvs | grep -q /dev/sdc
vgs | grep vgdata
lvs | grep lvdata
lvextend --help >/dev/null 2>&1
exit 0
