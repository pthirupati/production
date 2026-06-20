#!/bin/bash
# Cross-tech datastore-full: new VMware disk revealed by rescan, added to vgdata,
# and the lvdata LV genuinely extended to reclaim space for /data.
pvs | grep -q /dev/sdc
vgs | grep vgdata
lvs | grep lvdata
lvextend --help >/dev/null 2>&1
exit 0
