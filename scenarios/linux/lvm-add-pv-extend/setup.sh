#!/bin/bash
set -e
dd if=/dev/zero of=/var/disk1.img bs=1M count=400 status=none
dd if=/dev/zero of=/var/disk2.img bs=1M count=350 status=none
D1=$(losetup -f --show /var/disk1.img)
D2=$(losetup -f --show /var/disk2.img)
parted -s "$D1" mklabel gpt && parted -s "$D1" mkpart primary 1MiB 100%
parted -s "$D2" mklabel gpt && parted -s "$D2" mkpart primary 1MiB 100%
sleep 1
P1="${D1}p1"; [ -b "$P1" ] || P1="${D1}1"
P2="${D2}p1"; [ -b "$P2" ] || P2="${D2}1"
pvcreate -y "$P1"
vgcreate fixitlab "$P1"
lvcreate -y -l 100%FREE -n datalv fixitlab
mkfs.xfs /dev/fixitlab/datalv
mkdir -p /data && mount /dev/fixitlab/datalv /data
dd if=/dev/zero of=/data/fill bs=1M count=360 status=none
echo "Disk2 $P2 is unused — add to VG and extend datalv"

