#!/bin/bash
set -e
. /opt/fixitlab/lab-loop.sh
LV_DEV="/dev/mapper/fixitlab-datalv"
P2=$(cat /etc/fixitlab-disk2-part 2>/dev/null || true)
if [ -z "$P2" ] || [ ! -b "$P2" ]; then
  D2=$(cat /etc/fixitlab-disk2-loop 2>/dev/null || true)
  if [ -z "$D2" ] || [ ! -b "$D2" ]; then
    D2=$(fixitlab_loop_attach /opt/fixitlab/backing/disk2.img 350M)
    echo "$D2" > /etc/fixitlab-disk2-loop
    parted -s "$D2" mklabel gpt 2>/dev/null || true
    parted -s "$D2" mkpart primary 1MiB 100% 2>/dev/null || true
    partprobe "$D2" 2>/dev/null || true
    sleep 1
  fi
  P2="${D2}p1"; [ -b "$P2" ] || P2="${D2}1"
  echo "$P2" > /etc/fixitlab-disk2-part
fi
[ -b "$P2" ] || { echo "second disk partition missing" >&2; exit 1; }
vgchange -ay fixitlab 2>/dev/null || true
[ -b "$LV_DEV" ] || LV_DEV="/dev/fixitlab/datalv"
mountpoint -q /data || mount "$LV_DEV" /data 2>/dev/null || true
wipefs -a "$P2" 2>/dev/null || true
pvcreate -y --metadatasize 128m -ff "$P2"
vgextend fixitlab "$P2"
lvextend -y -l +100%FREE "$LV_DEV"
xfs_growfs /data
