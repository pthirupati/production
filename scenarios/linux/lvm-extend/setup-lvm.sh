#!/bin/bash
# Initialize loop-backed LVM: small LV on /data — user must extend
set -e
LV_DEV="/dev/mapper/fixitlab-datalv"

if [ -f /etc/lvm/lvm.conf ]; then
  sed -i 's/^\s*use_lvmetad\s*=\s*1/use_lvmetad = 0/' /etc/lvm/lvm.conf 2>/dev/null || true
fi

if vgs fixitlab >/dev/null 2>&1 && lvs fixitlab/datalv >/dev/null 2>&1; then
  [ -b "$LV_DEV" ] || LV_DEV="/dev/fixitlab/datalv"
  mkdir -p /data
  mountpoint -q /data || mount "$LV_DEV" /data
  exit 0
fi

vgchange -an fixitlab 2>/dev/null || true
vgremove -ff fixitlab 2>/dev/null || true
modprobe dm-mod 2>/dev/null || true

[ -f /var/lvm-backing.img ] || dd if=/dev/zero of=/var/lvm-backing.img bs=1M count=512 status=none
losetup -j /var/lvm-backing.img 2>/dev/null | cut -d: -f1 | while read -r loop; do
  [ -n "$loop" ] && losetup -d "$loop" 2>/dev/null || true
done

DEV=$(losetup -f --show /var/lvm-backing.img)
echo "$DEV" > /etc/fixitlab-lvm-dev

wipefs -a "$DEV" 2>/dev/null || true
pvcreate -y --metadatasize 128m -ff "$DEV"
vgcreate -y fixitlab "$DEV"
lvcreate -y -L 180M -n datalv fixitlab || lvcreate -y -l 50%VG -n datalv fixitlab
vgchange -ay fixitlab
udevadm settle 2>/dev/null || sleep 2
[ -b "$LV_DEV" ] || LV_DEV="/dev/fixitlab/datalv"
[ -b "$LV_DEV" ] || { echo "datalv device not found after lvcreate" >&2; exit 1; }

mkfs.xfs -f "$LV_DEV"
mkdir -p /data
mount "$LV_DEV" /data
grep -q '/dev/fixitlab/datalv' /etc/fstab || \
  echo "/dev/fixitlab/datalv /data xfs defaults 0 0" >> /etc/fstab
dd if=/dev/zero of=/data/app.img bs=1M count=170 status=none 2>/dev/null || true
echo "LVM ready: VG fixitlab has free space — extend datalv and resize filesystem"
