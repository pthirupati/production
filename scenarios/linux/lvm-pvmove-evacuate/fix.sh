#!/bin/bash
set -e
. /opt/fixitlab/lab-loop.sh
LV_DEV="/dev/mapper/fixitlab-datalv"
LV_ALT="/dev/fixitlab/datalv"
OP=$(cat /etc/fixitlab-old-loop 2>/dev/null || true)
NP=$(cat /etc/fixitlab-new-loop 2>/dev/null || true)
if [ -z "$OP" ] || [ ! -b "$OP" ]; then
  OP=$(fixitlab_loop_attach /opt/fixitlab/backing/old.img 200M)
  echo "$OP" > /etc/fixitlab-old-loop
fi
if [ -z "$NP" ] || [ ! -b "$NP" ]; then
  NP=$(fixitlab_loop_attach /opt/fixitlab/backing/new.img 200M)
  echo "$NP" > /etc/fixitlab-new-loop
fi
vgchange -ay fixitlab 2>/dev/null || true
fixitlab_lvm_wait_lv "$LV_DEV" "$LV_ALT" || true
[ -b "$LV_DEV" ] || LV_DEV="$LV_ALT"
mkdir -p /data
mountpoint -q /data || mount "$LV_DEV" /data
pvmove "$OP" "$NP"
vgreduce fixitlab "$OP"
pvremove -y "$OP"
