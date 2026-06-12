#!/bin/bash
set -e
LV_DEV="/dev/mapper/fixitlab-datalv"

if [ -f /etc/lvm/lvm.conf ]; then
  sed -i 's/^\s*use_lvmetad\s*=\s*1/use_lvmetad = 0/' /etc/lvm/lvm.conf 2>/dev/null || true
fi

if vgs fixitlab >/dev/null 2>&1 && lvs fixitlab/datalv >/dev/null 2>&1 && [ -f /data/important.db ]; then
  [ -b "$LV_DEV" ] || LV_DEV="/dev/fixitlab/datalv"
  mountpoint -q /data || mount "$LV_DEV" /data 2>/dev/null || true
  exit 0
fi

vgchange -an fixitlab 2>/dev/null || true
vgremove -ff fixitlab 2>/dev/null || true
modprobe dm-mod 2>/dev/null || true

dd if=/dev/zero of=/var/old.img bs=1M count=200 status=none
dd if=/dev/zero of=/var/new.img bs=1M count=200 status=none
OLD=$(losetup -f --show /var/old.img)
NEW=$(losetup -f --show /var/new.img)

for D in "$OLD" "$NEW"; do
  parted -s "$D" mklabel gpt
  parted -s "$D" mkpart primary 1MiB 100%
done
partprobe "$OLD" "$NEW" 2>/dev/null || true
sleep 2
OP="${OLD}p1"; [ -b "$OP" ] || OP="${OLD}1"
NP="${NEW}p1"; [ -b "$NP" ] || NP="${NEW}1"
[ -b "$OP" ] && [ -b "$NP" ] || { echo "partition devices missing" >&2; exit 1; }
echo "$OP" > /etc/fixitlab-old-part
echo "$NP" > /etc/fixitlab-new-part

wipefs -a "$OP" "$NP" 2>/dev/null || true
pvcreate -y --metadatasize 128m -ff "$OP" "$NP"
vgcreate -y fixitlab "$OP" "$NP"
lvcreate -y -l 100%FREE -n datalv fixitlab
vgchange -ay fixitlab
udevadm settle 2>/dev/null || sleep 2
[ -b "$LV_DEV" ] || LV_DEV="/dev/fixitlab/datalv"
mkfs.xfs -f "$LV_DEV"
mkdir -p /data && mount "$LV_DEV" /data
echo "production data" > /data/important.db
grep -q '/dev/fixitlab/datalv' /etc/fstab || \
  echo "/dev/fixitlab/datalv /data xfs defaults 0 0" >> /etc/fstab
echo "Evacuate $OP before removal — use pvmove"
