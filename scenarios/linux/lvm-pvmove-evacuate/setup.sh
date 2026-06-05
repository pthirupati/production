#!/bin/bash
set -e
dd if=/dev/zero of=/var/old.img bs=1M count=200 status=none
dd if=/dev/zero of=/var/new.img bs=1M count=200 status=none
OLD=$(losetup -f --show /var/old.img)
NEW=$(losetup -f --show /var/new.img)
for D in "$OLD" "$NEW"; do
  parted -s "$D" mklabel gpt && parted -s "$D" mkpart primary 1MiB 100%
done
sleep 1
OP="${OLD}p1"; [ -b "$OP" ] || OP="${OLD}1"
NP="${NEW}p1"; [ -b "$NP" ] || NP="${NEW}1"
pvcreate -y "$OP" "$NP"
vgcreate fixitlab "$OP" "$NP"
lvcreate -y -l 100%FREE -n datalv fixitlab
mkfs.xfs /dev/fixitlab/datalv
mkdir -p /data && mount /dev/fixitlab/datalv /data
echo "production data" > /data/important.db
echo "Evacuate $OP before removal — use pvmove"

