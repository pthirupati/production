#!/bin/bash
set -e
OLD=$(losetup -j /var/old.img 2>/dev/null | cut -d: -f1 | head -1)
OLD_P="${OLD}p1"
[ -b "$OLD_P" ] || OLD_P="${OLD}1"
NEW_P=$(pvs --noheadings -o pv_name --select vg_name=fixitlab 2>/dev/null | tr -d ' ' | grep -v "^${OLD_P}$" | head -1)
if [ -n "$NEW_P" ]; then
  pvmove "$OLD_P" "$NEW_P" 2>/dev/null || pvmove "$OLD_P" 2>/dev/null || true
fi
mountpoint -q /data || mount /dev/fixitlab/datalv /data 2>/dev/null || mount /data 2>/dev/null || true
