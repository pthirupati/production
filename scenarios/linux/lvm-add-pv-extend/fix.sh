#!/bin/bash
set -e
LV_DEV="/dev/mapper/fixitlab-datalv"
[ -x /opt/fixitlab/setup.sh ] && bash /opt/fixitlab/setup.sh
P2=$(cat /etc/fixitlab-disk2-part 2>/dev/null || true)
if [ -z "$P2" ] || [ ! -b "$P2" ]; then
  D2=$(losetup -j /var/disk2.img 2>/dev/null | cut -d: -f1 | head -1)
  P2="${D2}p1"; [ -b "$P2" ] || P2="${D2}1"
fi
[ -b "$P2" ] || { partprobe 2>/dev/null || true; sleep 2; [ -b "$P2" ] || exit 1; }
pvcreate -y -ff "$P2"
vgextend fixitlab "$P2"
lvextend -y -l +100%FREE "$LV_DEV"
[ -b "$LV_DEV" ] || LV_DEV="/dev/fixitlab/datalv"
mkdir -p /data
mountpoint -q /data || mount "$LV_DEV" /data
xfs_growfs /data 2>/dev/null || resize2fs "$LV_DEV" 2>/dev/null || true
