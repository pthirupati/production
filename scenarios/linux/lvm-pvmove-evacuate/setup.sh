#!/bin/bash
set -e
. /opt/fixitlab/lab-loop.sh
LV_DEV="/dev/mapper/fixitlab-datalv"
LV_ALT="/dev/fixitlab/datalv"

if [ -f /etc/lvm/lvm.conf ]; then
  sed -i 's/^\s*use_lvmetad\s*=\s*1/use_lvmetad = 0/' /etc/lvm/lvm.conf 2>/dev/null || true
fi

if vgs fixitlab >/dev/null 2>&1 && lvs fixitlab/datalv >/dev/null 2>&1 && [ -f /data/important.db ]; then
  NP=$(cat /etc/fixitlab-new-loop 2>/dev/null || true)
  if [ -n "$NP" ] && pvs "$NP" >/dev/null 2>&1; then
    FREE=$(pvs --noheadings -o pv_free --units m --nosuffix "$NP" 2>/dev/null | tr -d ' ' | cut -d. -f1)
    if [ "${FREE:-0}" -ge 100 ]; then
      fixitlab_lvm_wait_lv "$LV_DEV" "$LV_ALT" || true
      [ -b "$LV_DEV" ] || LV_DEV="$LV_ALT"
      mountpoint -q /data || mount "$LV_DEV" /data 2>/dev/null || true
      exit 0
    fi
  fi
fi

fixitlab_lvm_teardown
fixitlab_loop_init

OLD=$(fixitlab_loop_attach /opt/fixitlab/backing/old.img 200M)
NEW=$(fixitlab_loop_attach /opt/fixitlab/backing/new.img 200M)
echo "$OLD" > /etc/fixitlab-old-loop
echo "$NEW" > /etc/fixitlab-new-loop

wipefs -a "$OLD" "$NEW" 2>/dev/null || true
pvcreate -y --metadatasize 64m -ff "$OLD"
vgcreate -y fixitlab "$OLD"
lvcreate -y -Zn -l 100%FREE -n datalv fixitlab
pvcreate -y --metadatasize 64m -ff "$NEW"
vgextend -y fixitlab "$NEW"
vgchange -ay fixitlab
fixitlab_lvm_wait_lv "$LV_DEV" "$LV_ALT" || { echo "datalv missing after lvcreate" >&2; exit 1; }
[ -b "$LV_DEV" ] || LV_DEV="$LV_ALT"
mkfs.xfs -f "$LV_DEV"
mkdir -p /data && mount "$LV_DEV" /data
echo "production data" > /data/important.db
grep -q '/dev/fixitlab/datalv' /etc/fstab || \
  echo "/dev/fixitlab/datalv /data xfs defaults 0 0" >> /etc/fstab
echo "Evacuate $OLD before removal — use pvmove"
