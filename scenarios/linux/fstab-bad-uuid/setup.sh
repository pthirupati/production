#!/bin/bash
set -e
. /opt/fixitlab/lab-loop.sh
if mountpoint -q /mnt/data 2>/dev/null && [ -f /mnt/data/production.dat ]; then
  exit 0
fi
fixitlab_loop_init
IMG=/opt/fixitlab/backing/data.img
DEV=$(fixitlab_loop_attach "$IMG" 80M)
mkfs.ext4 -F "$DEV"
mkdir -p /mnt/data
REAL_UUID=$(blkid -s UUID -o value "$DEV")
echo "critical" > /tmp/production.dat
mount "$DEV" /mnt/data && mv /tmp/production.dat /mnt/data/ && umount /mnt/data
echo "$DEV" > /etc/fixitlab-data-dev
echo "UUID=00000000-0000-0000-0000-000000000000 /mnt/data ext4 defaults 0 2" >> /etc/fstab
echo "Real UUID is $REAL_UUID but fstab has wrong value"
