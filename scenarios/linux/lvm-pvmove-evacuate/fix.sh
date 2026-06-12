#!/bin/bash
set -e
LV_DEV="/dev/mapper/fixitlab-datalv"
OLD_P=$(cat /etc/fixitlab-old-part 2>/dev/null || true)
NEW_P=$(cat /etc/fixitlab-new-part 2>/dev/null || true)
if [ -z "$OLD_P" ] || [ ! -b "$OLD_P" ]; then
  OLD=$(losetup -j /opt/fixitlab/backing/old.img 2>/dev/null | cut -d: -f1 | head -1)
  [ -n "$OLD" ] && [ -b "$OLD" ] || { [ -f /opt/fixitlab/backing/old.img ] && OLD=$(losetup -f --show /opt/fixitlab/backing/old.img); }
  OLD_P="${OLD}p1"; [ -b "$OLD_P" ] || OLD_P="${OLD}1"
fi
if [ -z "$NEW_P" ] || [ ! -b "$NEW_P" ]; then
  NEW=$(losetup -j /opt/fixitlab/backing/new.img 2>/dev/null | cut -d: -f1 | head -1)
  [ -n "$NEW" ] && [ -b "$NEW" ] || { [ -f /opt/fixitlab/backing/new.img ] && NEW=$(losetup -f --show /opt/fixitlab/backing/new.img); }
  NEW_P="${NEW}p1"; [ -b "$NEW_P" ] || NEW_P="${NEW}1"
fi
[ -b "$OLD_P" ] && [ -b "$NEW_P" ] || exit 1
pvmove -n fixitlab "$OLD_P" "$NEW_P" || pvmove "$OLD_P" "$NEW_P" || pvmove "$OLD_P"
[ -b "$LV_DEV" ] || LV_DEV="/dev/fixitlab/datalv"
mkdir -p /data
mountpoint -q /data || mount "$LV_DEV" /data
