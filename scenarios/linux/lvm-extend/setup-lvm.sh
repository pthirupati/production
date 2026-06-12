#!/bin/bash
# Initialize loop-backed LVM: small LV on /data — user must extend
set -e
. /opt/fixitlab/lab-loop.sh
LV_DEV="/dev/mapper/fixitlab-datalv"
LV_ALT="/dev/fixitlab/datalv"

if [ -f /etc/lvm/lvm.conf ]; then
  sed -i 's/^\s*use_lvmetad\s*=\s*1/use_lvmetad = 0/' /etc/lvm/lvm.conf 2>/dev/null || true
fi

if vgs fixitlab >/dev/null 2>&1 && lvs fixitlab/datalv >/dev/null 2>&1; then
  fixitlab_lvm_wait_lv "$LV_DEV" "$LV_ALT" || true
  [ -b "$LV_DEV" ] || LV_DEV="$LV_ALT"
  mkdir -p /data
  mountpoint -q /data || mount "$LV_DEV" /data 2>/dev/null || true
  exit 0
fi

vgchange -an fixitlab 2>/dev/null || true
vgremove -ff fixitlab 2>/dev/null || true
fixitlab_loop_init

IMG=/opt/fixitlab/backing/lvm-backing.img
fixitlab_loop_detach_image "$IMG"
DEV=$(fixitlab_loop_attach "$IMG" 768M)
echo "$DEV" > /etc/fixitlab-lvm-dev

wipefs -a "$DEV" 2>/dev/null || true
pvcreate -y --metadatasize 64m -ff "$DEV"
vgcreate -y fixitlab "$DEV"
lvcreate -y -Zn -L 180M -n datalv fixitlab
vgchange -ay fixitlab 2>&1
fixitlab_lvm_wait_lv "$LV_DEV" "$LV_ALT" || { echo "datalv device not found after lvcreate" >&2; exit 1; }
[ -b "$LV_DEV" ] || LV_DEV="$LV_ALT"

mkfs.xfs -f "$LV_DEV"
mkdir -p /data
mount "$LV_DEV" /data
grep -q '/dev/fixitlab/datalv' /etc/fstab || \
  echo "/dev/fixitlab/datalv /data xfs defaults 0 0" >> /etc/fstab
dd if=/dev/zero of=/data/app.img bs=1M count=170 status=none 2>/dev/null || true
echo "LVM ready: VG fixitlab has free space — extend datalv and resize filesystem"
