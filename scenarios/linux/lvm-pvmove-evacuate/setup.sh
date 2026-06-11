#!/bin/bash
set -e
if vgs fixitlab >/dev/null 2>&1 && lvs fixitlab/datalv >/dev/null 2>&1 && [ -f /data/important.db ]; then
  mountpoint -q /data || mount /dev/fixitlab/datalv /data 2>/dev/null || true
  exit 0
fi
dd if=/dev/zero of=/var/old.img bs=1M count=200 status=none
dd if=/dev/zero of=/var/new.img bs=1M count=200 status=none
OLD=$(losetup -j /var/old.img 2>/dev/null | cut -d: -f1 | head -1)
NEW=$(losetup -j /var/new.img 2>/dev/null | cut -d: -f1 | head -1)
[ -n "$OLD" ] || OLD=$(losetup -f --show /var/old.img)
[ -n "$NEW" ] || NEW=$(losetup -f --show /var/new.img)
for D in "$OLD" "$NEW"; do
  parted -s "$D" mklabel gpt 2>/dev/null || true
  parted -s "$D" mkpart primary 1MiB 100% 2>/dev/null || true
done
partprobe "$OLD" "$NEW" 2>/dev/null || true
sleep 2
OP="${OLD}p1"; [ -b "$OP" ] || OP="${OLD}1"
NP="${NEW}p1"; [ -b "$NP" ] || NP="${NEW}1"
echo "$OP" > /etc/fixitlab-old-part
echo "$NP" > /etc/fixitlab-new-part
pvcreate -y -ff "$OP" "$NP" 2>/dev/null || pvcreate -y "$OP" "$NP"
vgcreate fixitlab "$OP" "$NP" 2>/dev/null || true
lvcreate -y -l 100%FREE -n datalv fixitlab 2>/dev/null || true
mkfs.xfs -f /dev/fixitlab/datalv 2>/dev/null || true
mkdir -p /data && mount /dev/fixitlab/datalv /data
echo "production data" > /data/important.db
grep -q '/dev/fixitlab/datalv' /etc/fstab || \
  echo "/dev/fixitlab/datalv /data xfs defaults 0 0" >> /etc/fstab
echo "Evacuate $OP before removal — use pvmove"
