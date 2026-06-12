#!/bin/bash
set -e
. /opt/fixitlab/lab-loop.sh
LV_DEV="/dev/mapper/fixitlab-datalv"
LV_ALT="/dev/fixitlab/datalv"
D2=$(cat /etc/fixitlab-disk2-loop 2>/dev/null || true)
if [ -z "$D2" ] || [ ! -b "$D2" ]; then
  D2=$(fixitlab_loop_attach /opt/fixitlab/backing/disk2.img 350M)
  echo "$D2" > /etc/fixitlab-disk2-loop
fi
[ -b "$D2" ] || { echo "second disk loop device missing" >&2; exit 1; }
vgchange -ay fixitlab 2>/dev/null || true
fixitlab_lvm_wait_lv "$LV_DEV" "$LV_ALT" || true
[ -b "$LV_DEV" ] || LV_DEV="$LV_ALT"
mkdir -p /data
mountpoint -q /data || mount "$LV_DEV" /data 2>/dev/null || true
wipefs -a "$D2" 2>/dev/null || true
pvcreate -y --metadatasize 128m -ff "$D2"
vgextend fixitlab "$D2"
lvextend -y -l +100%FREE "$LV_DEV"
xfs_growfs /data
