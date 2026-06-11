#!/bin/bash
# Initialize loop-backed LVM: small LV on /data — user must extend
set -e
if vgs fixitlab >/dev/null 2>&1 && lvs fixitlab/datalv >/dev/null 2>&1; then
  mountpoint -q /data || mount /dev/fixitlab/datalv /data 2>/dev/null || true
  exit 0
fi
dd if=/dev/zero of=/var/lvm-backing.img bs=1M count=512 status=none conv=notrunc 2>/dev/null || \
  dd if=/dev/zero of=/var/lvm-backing.img bs=1M count=512 status=none
DEV=$(losetup -j /var/lvm-backing.img 2>/dev/null | cut -d: -f1 | head -1)
[ -n "$DEV" ] || DEV=$(losetup -f --show /var/lvm-backing.img)
pvcreate -y -ff "$DEV" 2>/dev/null || pvcreate -y "$DEV"
vgcreate fixitlab "$DEV" 2>/dev/null || vgchange -ay fixitlab 2>/dev/null || true
lvcreate -y -L 180M -n datalv fixitlab 2>/dev/null || true
mkfs.xfs -f /dev/fixitlab/datalv 2>/dev/null || true
mkdir -p /data
mount /dev/fixitlab/datalv /data 2>/dev/null || true
grep -q '/dev/fixitlab/datalv' /etc/fstab || \
  echo "/dev/fixitlab/datalv /data xfs defaults 0 0" >> /etc/fstab
dd if=/dev/zero of=/data/app.img bs=1M count=170 status=none 2>/dev/null || true
echo "LVM ready: VG fixitlab has free space — extend datalv and resize filesystem"
