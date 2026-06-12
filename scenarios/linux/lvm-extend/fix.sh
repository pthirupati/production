#!/bin/bash
set -e
LV_DEV="/dev/mapper/fixitlab-datalv"
# Ensure LVM stack exists (setup may have been skipped or partially failed)
if [ -x /opt/fixitlab/setup.sh ]; then
  bash /opt/fixitlab/setup.sh
fi
[ -b "$LV_DEV" ] || LV_DEV="/dev/fixitlab/datalv"
if ! lvs fixitlab/datalv >/dev/null 2>&1; then
  echo "Logical volume datalv not found — re-run setup-lvm.sh" >&2
  exit 1
fi
lvextend -y -L 350M "$LV_DEV"
vgchange -ay fixitlab
mkdir -p /data
mountpoint -q /data || mount "$LV_DEV" /data
xfs_growfs /data 2>/dev/null || resize2fs "$LV_DEV" 2>/dev/null || true
