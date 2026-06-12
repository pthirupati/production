#!/bin/bash
set -e
. /opt/fixitlab/lab-loop.sh
LV_DEV="/dev/mapper/fixitlab-datalv"
OP=$(cat /etc/fixitlab-old-part 2>/dev/null || true)
NP=$(cat /etc/fixitlab-new-part 2>/dev/null || true)
if [ -z "$OP" ] || [ ! -b "$OP" ]; then
  OLD=$(fixitlab_loop_attach /opt/fixitlab/backing/old.img 200M)
  parted -s "$OLD" mklabel gpt 2>/dev/null || true
  parted -s "$OLD" mkpart primary 1MiB 100% 2>/dev/null || true
  partprobe "$OLD" 2>/dev/null || true
  OP="${OLD}p1"; [ -b "$OP" ] || OP="${OLD}1"
  echo "$OP" > /etc/fixitlab-old-part
fi
if [ -z "$NP" ] || [ ! -b "$NP" ]; then
  NEW=$(fixitlab_loop_attach /opt/fixitlab/backing/new.img 200M)
  parted -s "$NEW" mklabel gpt 2>/dev/null || true
  parted -s "$NEW" mkpart primary 1MiB 100% 2>/dev/null || true
  partprobe "$NEW" 2>/dev/null || true
  NP="${NEW}p1"; [ -b "$NP" ] || NP="${NEW}1"
  echo "$NP" > /etc/fixitlab-new-part
fi
vgchange -ay fixitlab 2>/dev/null || true
[ -b "$LV_DEV" ] || LV_DEV="/dev/fixitlab/datalv"
mountpoint -q /data || mount "$LV_DEV" /data
pvmove "$OP" "$NP"
vgreduce fixitlab "$OP"
pvremove -y "$OP"
