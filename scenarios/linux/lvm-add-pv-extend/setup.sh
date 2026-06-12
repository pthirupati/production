#!/bin/bash
set -e
LV_DEV="/dev/mapper/fixitlab-datalv"
if vgs fixitlab >/dev/null 2>&1 && lvs fixitlab/datalv >/dev/null 2>&1; then
  [ -b "$LV_DEV" ] || LV_DEV="/dev/fixitlab/datalv"
  mountpoint -q /data || mount "$LV_DEV" /data 2>/dev/null || true
  exit 0
fi

vgremove -ff fixitlab 2>/dev/null || true
modprobe dm-mod 2>/dev/null || true

dd if=/dev/zero of=/var/disk1.img bs=1M count=400 status=none
dd if=/dev/zero of=/var/disk2.img bs=1M count=350 status=none
D1=$(losetup -j /var/disk1.img 2>/dev/null | cut -d: -f1 | head -1)
D2=$(losetup -j /var/disk2.img 2>/dev/null | cut -d: -f1 | head -1)
[ -n "$D1" ] || D1=$(losetup -f --show /var/disk1.img)
[ -n "$D2" ] || D2=$(losetup -f --show /var/disk2.img)

parted -s "$D1" mklabel gpt
parted -s "$D1" mkpart primary 1MiB 100%
parted -s "$D2" mklabel gpt
parted -s "$D2" mkpart primary 1MiB 100%
partprobe "$D1" "$D2" 2>/dev/null || true
sleep 2
P1="${D1}p1"; [ -b "$P1" ] || P1="${D1}1"
P2="${D2}p1"; [ -b "$P2" ] || P2="${D2}1"
[ -b "$P1" ] && [ -b "$P2" ] || { echo "partition devices missing" >&2; exit 1; }
echo "$P2" > /etc/fixitlab-disk2-part

pvcreate -y -ff "$P1"
vgcreate fixitlab "$P1"
lvcreate -y -l 100%FREE -n datalv fixitlab
vgchange -ay fixitlab
udevadm settle 2>/dev/null || sleep 2
LV_DEV="/dev/mapper/fixitlab-datalv"
[ -b "$LV_DEV" ] || LV_DEV="/dev/fixitlab/datalv"
mkfs.xfs -f "$LV_DEV"
mkdir -p /data && mount "$LV_DEV" /data
dd if=/dev/zero of=/data/fill bs=1M count=360 status=none 2>/dev/null || true
echo "Disk2 $P2 is unused — add to VG and extend datalv"
