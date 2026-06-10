#!/bin/bash
# Initialize loop-backed LVM: small LV on /data — user must extend
set -e
dd if=/dev/zero of=/var/lvm-backing.img bs=1M count=512 status=none
DEV=$(losetup -f --show /var/lvm-backing.img)
pvcreate -y "$DEV"
vgcreate fixitlab "$DEV"
lvcreate -y -L 180M -n datalv fixitlab
mkfs.xfs -f /dev/fixitlab/datalv
mkdir -p /data
mount /dev/fixitlab/datalv /data
echo "/dev/fixitlab/datalv /data xfs defaults 0 0" >> /etc/fstab
dd if=/dev/zero of=/data/app.img bs=1M count=170 status=none
echo "LVM ready: VG fixitlab has free space — extend datalv and resize filesystem"
