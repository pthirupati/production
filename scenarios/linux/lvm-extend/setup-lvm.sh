#!/bin/bash
# Initialize loop-backed LVM: small LV on /data — user must extend
set -e
LOOP=/dev/loop99
[ -b "$LOOP" ] || mknod "$LOOP" b 7 99 2>/dev/null || true
dd if=/dev/zero of=/var/lvm-backing.img bs=1M count=512 status=none
losetup "$LOOP" /var/lvm-backing.img 2>/dev/null || losetup -f /var/lvm-backing.img
DEV=$(losetup -j /var/lvm-backing.img | awk -F: '{print $1}' | head -1)
[ -n "$DEV" ] || DEV=$(losetup -a | grep lvm-backing | cut -d: -f1)
parted -s "$DEV" mklabel gpt
parted -s "$DEV" mkpart primary 1MiB 100%
partprobe "$DEV" 2>/dev/null || true
sleep 1
PV_PART="${DEV}p1"
[ -b "$PV_PART" ] || PV_PART="${DEV}1"
pvcreate -y "$PV_PART"
vgcreate fixitlab "$PV_PART"
lvcreate -y -L 180M -n datalv fixitlab
mkfs.xfs /dev/fixitlab/datalv
mkdir -p /data
mount /dev/fixitlab/datalv /data
echo "/dev/fixitlab/datalv /data xfs defaults 0 0" >> /etc/fstab
dd if=/dev/zero of=/data/app.img bs=1M count=170 status=none
echo "LVM ready: VG fixitlab has free space — extend datalv and resize filesystem"
