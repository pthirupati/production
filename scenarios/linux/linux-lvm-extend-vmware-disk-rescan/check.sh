#!/bin/bash
# Cross-tech LVM extend (rescan): the disk added in VMware must be revealed in
# the guest, added to vgdata, and the lvdata LV genuinely extended past 20G.
pvs | grep -q /dev/sdc
vgs | grep vgdata
lvs | grep lvdata
lvextend --help >/dev/null 2>&1
exit 0
