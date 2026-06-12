#!/bin/bash
set -e
LV_DEV="/dev/mapper/fixitlab-datalv"
[ -b "$LV_DEV" ] || LV_DEV="/dev/fixitlab/datalv"
if ! lvs fixitlab/datalv >/dev/null 2>&1; then
  echo "Logical volume datalv not found — run setup-lvm.sh first" >&2
  exit 1
fi
vgchange -ay fixitlab 2>/dev/null || true
lvextend -y -L 350M "$LV_DEV"
mkdir -p /data
mountpoint -q /data || mount "$LV_DEV" /data
xfs_growfs /data 2>/dev/null || resize2fs "$LV_DEV" 2>/dev/null || true
