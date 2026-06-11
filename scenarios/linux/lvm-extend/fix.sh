#!/bin/bash
set -e
# Ensure LVM stack exists (setup may have been skipped or partially failed)
if [ -x /opt/fixitlab/setup.sh ]; then
  bash /opt/fixitlab/setup.sh
fi
if ! lvs fixitlab/datalv >/dev/null 2>&1; then
  echo "Logical volume datalv not found — re-run setup-lvm.sh" >&2
  exit 1
fi
lvextend -y -L 350M /dev/fixitlab/datalv
mountpoint -q /data || mount /dev/fixitlab/datalv /data
xfs_growfs /data 2>/dev/null || resize2fs /dev/fixitlab/datalv 2>/dev/null || true
