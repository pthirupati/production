#!/bin/bash
set -e
LV_DEV="/dev/mapper/fixitlab-datalv"
P2=$(cat /etc/fixitlab-disk2-part 2>/dev/null || true)
if [ -z "$P2" ] || [ ! -b "$P2" ]; then
  D2=$(cat /etc/fixitlab-disk2-loop 2>/dev/null || true)
  [ -n "$D2" ] && [ -b "$D2" ] || D2=$(losetup -j /var/disk2.img 2>/dev/null | cut -d: -f1 | head -1)
  if [ -z "$D2" ] && [ -f /var/disk2.img ]; then
    D2=$(losetup -f --show /var/disk2.img)
  fi
  P2="${D2}p1"; [ -b "$P2" ] || P2="${D2}1"
  [ -b "$P2" ] && echo "$P2" > /etc/fixitlab-disk2-part
fi
[ -b "$P2" ] || { partprobe 2>/dev/null || true; sleep 2; [ -b "$P2" ] || exit 1; }
pvcreate -y -ff "$P2"
vgextend fixitlab "$P2"
lvextend -y -l +100%FREE "$LV_DEV"
[ -b "$LV_DEV" ] || LV_DEV="/dev/fixitlab/datalv"
mkdir -p /data
mountpoint -q /data || mount "$LV_DEV" /data
xfs_growfs /data 2>/dev/null || resize2fs "$LV_DEV" 2>/dev/null || true
