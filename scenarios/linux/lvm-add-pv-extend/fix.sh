#!/bin/bash
set -e
for p in /dev/loop*p1 /dev/loop*1; do
  [ -b "$p" ] || continue
  pvs "$p" >/dev/null 2>&1 || pvcreate -y "$p" 2>/dev/null || true
  vgdisplay fixitlab >/dev/null 2>&1 && vgextend fixitlab "$p" 2>/dev/null || true
done
lvextend -y -l +100%FREE /dev/fixitlab/datalv 2>/dev/null || true
mountpoint -q /data || mount /data 2>/dev/null || true
xfs_growfs /data 2>/dev/null || true
