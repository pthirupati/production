#!/bin/bash
set -e
LV_DEV="/dev/mapper/fixitlab-datalv"
[ -x /opt/fixitlab/setup.sh ] && bash /opt/fixitlab/setup.sh
OLD_P=$(cat /etc/fixitlab-old-part 2>/dev/null || true)
NEW_P=$(cat /etc/fixitlab-new-part 2>/dev/null || true)
if [ -z "$OLD_P" ]; then
  OLD=$(losetup -j /var/old.img 2>/dev/null | cut -d: -f1 | head -1)
  OLD_P="${OLD}p1"; [ -b "$OLD_P" ] || OLD_P="${OLD}1"
fi
if [ -z "$NEW_P" ]; then
  NEW=$(losetup -j /var/new.img 2>/dev/null | cut -d: -f1 | head -1)
  NEW_P="${NEW}p1"; [ -b "$NEW_P" ] || NEW_P="${NEW}1"
fi
[ -b "$OLD_P" ] && [ -b "$NEW_P" ] || exit 1
pvmove -n fixitlab "$OLD_P" "$NEW_P" || pvmove "$OLD_P" "$NEW_P" || pvmove "$OLD_P"
[ -b "$LV_DEV" ] || LV_DEV="/dev/fixitlab/datalv"
mkdir -p /data
mountpoint -q /data || mount "$LV_DEV" /data
