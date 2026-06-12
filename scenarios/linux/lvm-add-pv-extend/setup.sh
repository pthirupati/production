#!/bin/bash
set -e
LV_DEV="/dev/mapper/fixitlab-datalv"

if [ -f /etc/lvm/lvm.conf ]; then
  sed -i 's/^\s*use_lvmetad\s*=\s*1/use_lvmetad = 0/' /etc/lvm/lvm.conf 2>/dev/null || true
fi

if vgs fixitlab >/dev/null 2>&1 && lvs fixitlab/datalv >/dev/null 2>&1 && [ -f /etc/fixitlab-disk2-part ]; then
  [ -b "$LV_DEV" ] || LV_DEV="/dev/fixitlab/datalv"
  mountpoint -q /data || mount "$LV_DEV" /data 2>/dev/null || true
  exit 0
fi

vgchange -an fixitlab 2>/dev/null || true
vgremove -ff fixitlab 2>/dev/null || true
modprobe dm-mod 2>/dev/null || true
mkdir -p /dev/mapper /opt/fixitlab/backing
dmsetup mknodes 2>/dev/null || true

dd if=/dev/zero of=/opt/fixitlab/backing/disk1.img bs=1M count=400 status=none
dd if=/dev/zero of=/opt/fixitlab/backing/disk2.img bs=1M count=350 status=none
D1=$(losetup -f --show /opt/fixitlab/backing/disk1.img)
D2=$(losetup -f --show /opt/fixitlab/backing/disk2.img)
echo "$D1" > /etc/fixitlab-disk1-loop
echo "$D2" > /etc/fixitlab-disk2-loop

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

wipefs -a "$P1" 2>/dev/null || true
pvcreate -y --metadatasize 128m -ff "$P1"
vgcreate -y fixitlab "$P1"
lvcreate -y -l 100%FREE -n datalv fixitlab
vgchange -ay fixitlab
udevadm settle 2>/dev/null || sleep 2
LV_DEV="/dev/mapper/fixitlab-datalv"
[ -b "$LV_DEV" ] || LV_DEV="/dev/fixitlab/datalv"
mkfs.xfs -f "$LV_DEV"
mkdir -p /data && mount "$LV_DEV" /data
dd if=/dev/zero of=/data/fill bs=1M count=360 status=none 2>/dev/null || true
echo "Disk2 $P2 is unused — add to VG and extend datalv"
