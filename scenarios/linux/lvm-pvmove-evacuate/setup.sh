#!/bin/bash
set -e
. /opt/fixitlab/lab-loop.sh
LV_DEV="/dev/mapper/fixitlab-datalv"
LV_ALT="/dev/fixitlab/datalv"

if [ -f /etc/lvm/lvm.conf ]; then
  sed -i 's/^\s*use_lvmetad\s*=\s*1/use_lvmetad = 0/' /etc/lvm/lvm.conf 2>/dev/null || true
fi

if vgs fixitlab >/dev/null 2>&1 && lvs fixitlab/datalv >/dev/null 2>&1 && [ -f /data/important.db ]; then
  fixitlab_lvm_wait_lv "$LV_DEV" "$LV_ALT" || true
  [ -b "$LV_DEV" ] || LV_DEV="$LV_ALT"
  mountpoint -q /data || mount "$LV_DEV" /data 2>/dev/null || true
  exit 0
fi

vgchange -an fixitlab 2>/dev/null || true
vgremove -ff fixitlab 2>/dev/null || true
fixitlab_loop_init

OLD=$(fixitlab_loop_attach /opt/fixitlab/backing/old.img 200M)
NEW=$(fixitlab_loop_attach /opt/fixitlab/backing/new.img 200M)

for D in "$OLD" "$NEW"; do
  parted -s "$D" mklabel gpt
  parted -s "$D" mkpart primary 1MiB 100%
done
OP=$(fixitlab_loop_partdev "$OLD" 1)
NP=$(fixitlab_loop_partdev "$NEW" 1)
echo "$OP" > /etc/fixitlab-old-part
echo "$NP" > /etc/fixitlab-new-part

wipefs -a "$OP" "$NP" 2>/dev/null || true
pvcreate -y --metadatasize 128m -ff "$OP" "$NP"
vgcreate -y fixitlab "$OP" "$NP"
lvcreate -y -Zn -l 100%FREE -n datalv fixitlab
vgchange -ay fixitlab
fixitlab_lvm_wait_lv "$LV_DEV" "$LV_ALT" || { echo "datalv missing after lvcreate" >&2; exit 1; }
[ -b "$LV_DEV" ] || LV_DEV="$LV_ALT"
mkfs.xfs -f "$LV_DEV"
mkdir -p /data && mount "$LV_DEV" /data
echo "production data" > /data/important.db
grep -q '/dev/fixitlab/datalv' /etc/fstab || \
  echo "/dev/fixitlab/datalv /data xfs defaults 0 0" >> /etc/fstab
echo "Evacuate $OP before removal — use pvmove"
