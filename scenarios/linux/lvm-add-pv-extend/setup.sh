#!/bin/bash
set -e
. /opt/fixitlab/lab-loop.sh
LV_DEV="/dev/mapper/fixitlab-datalv"
LV_ALT="/dev/fixitlab/datalv"

if [ -f /etc/lvm/lvm.conf ]; then
  sed -i 's/^\s*use_lvmetad\s*=\s*1/use_lvmetad = 0/' /etc/lvm/lvm.conf 2>/dev/null || true
fi

if vgs fixitlab >/dev/null 2>&1 && lvs fixitlab/datalv >/dev/null 2>&1 && [ -f /etc/fixitlab-disk2-loop ]; then
  D2=$(cat /etc/fixitlab-disk2-loop)
  [ -b "$D2" ] && ln -sf "$D2" /dev/fixitlab-disk2 2>/dev/null || true
  fixitlab_lvm_wait_lv "$LV_DEV" "$LV_ALT" || true
  [ -b "$LV_DEV" ] || LV_DEV="$LV_ALT"
  mountpoint -q /data || mount "$LV_DEV" /data 2>/dev/null || true
  exit 0
fi

vgchange -an fixitlab 2>/dev/null || true
vgremove -ff fixitlab 2>/dev/null || true
fixitlab_loop_init

D1=$(fixitlab_loop_attach /opt/fixitlab/backing/disk1.img 400M)
D2=$(fixitlab_loop_attach /opt/fixitlab/backing/disk2.img 400M)
echo "$D1" > /etc/fixitlab-disk1-loop
echo "$D2" > /etc/fixitlab-disk2-loop
ln -sf "$D2" /dev/fixitlab-disk2

wipefs -a "$D1" 2>/dev/null || true
pvcreate -y --metadatasize 128m -ff "$D1"
vgcreate -y fixitlab "$D1"
lvcreate -y -Zn -l 100%FREE -n datalv fixitlab
vgchange -ay fixitlab
fixitlab_lvm_wait_lv "$LV_DEV" "$LV_ALT" || { echo "datalv missing after lvcreate" >&2; exit 1; }
[ -b "$LV_DEV" ] || LV_DEV="$LV_ALT"
mkfs.xfs -f "$LV_DEV"
mkdir -p /data && mount "$LV_DEV" /data
dd if=/dev/zero of=/data/fill bs=1M count=360 status=none 2>/dev/null || true
echo "New disk ready at /dev/fixitlab-disk2 ($D2) — not yet in volume group"
