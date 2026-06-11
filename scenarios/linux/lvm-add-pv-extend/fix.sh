#!/bin/bash
set -e
[ -x /opt/fixitlab/setup.sh ] && bash /opt/fixitlab/setup.sh 2>/dev/null || true
D2=$(losetup -j /var/disk2.img 2>/dev/null | cut -d: -f1 | head -1)
P2="${D2}p1"
[ -b "$P2" ] || P2="${D2}1"
[ -b "$P2" ] || { echo "partition $P2 not found"; exit 1; }
pvcreate -y -ff "$P2" 2>/dev/null || pvcreate -y "$P2"
vgextend fixitlab "$P2"
lvextend -y -l +100%FREE /dev/fixitlab/datalv
mountpoint -q /data || mount /dev/fixitlab/datalv /data 2>/dev/null || mount /data
xfs_growfs /data 2>/dev/null || resize2fs /dev/fixitlab/datalv 2>/dev/null || true
