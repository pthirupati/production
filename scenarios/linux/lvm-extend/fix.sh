#!/bin/bash
set -e
. /opt/fixitlab/lab-loop.sh
LV_DEV="/dev/mapper/fixitlab-datalv"
LV_ALT="/dev/fixitlab/datalv"
if ! lvs fixitlab/datalv >/dev/null 2>&1; then
  echo "Logical volume datalv not found — run setup-lvm.sh first" >&2
  exit 1
fi
vgchange -ay fixitlab 2>/dev/null || true
fixitlab_lvm_wait_lv "$LV_DEV" "$LV_ALT" || true
[ -b "$LV_DEV" ] || LV_DEV="$LV_ALT"
[ -b "$LV_DEV" ] || { echo "datalv block device missing" >&2; exit 1; }
lvextend -y -L 350M "$LV_DEV"
mkdir -p /data
if ! mountpoint -q /data; then
  if ! blkid "$LV_DEV" >/dev/null 2>&1; then
    mkfs.xfs -f "$LV_DEV"
  fi
  mount "$LV_DEV" /data
fi
xfs_growfs /data 2>/dev/null || resize2fs "$LV_DEV" 2>/dev/null || true
