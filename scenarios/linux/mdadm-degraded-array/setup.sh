#!/bin/bash
set -e
. /opt/fixitlab/lab-loop.sh
if grep -q 'md0' /proc/mdstat 2>/dev/null && [ -f /etc/fixitlab-raid-spare ]; then
  mountpoint -q /data || mount /dev/md0 /data 2>/dev/null || true
  exit 0
fi

fixitlab_loop_init
fixitlab_mdadm_cleanup
D1=$(fixitlab_loop_attach /opt/fixitlab/backing/raid1.img 120M)
D2=$(fixitlab_loop_attach /opt/fixitlab/backing/raid2.img 120M)
echo "$D1" > /etc/fixitlab-raid1-loop
echo "$D2" > /etc/fixitlab-raid2-loop
echo yes | mdadm --create /dev/md0 --level=1 --raid-devices=2 "$D1" "$D2"
sleep 2
mkfs.ext4 -F /dev/md0
mkdir -p /data && mount /dev/md0 /data
echo "raid data" > /data/important.txt
mdadm /dev/md0 --fail "$D2" 2>/dev/null || true
mdadm /dev/md0 --remove "$D2" 2>/dev/null || true
echo "$D2" > /etc/fixitlab-raid-spare
echo "RAID degraded — add $D2 back with mdadm --manage /dev/md0 --add"
