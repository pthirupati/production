#!/bin/bash
FAILED=0
PV_COUNT=$(pvs --noheadings -o pv_name --select vg_name=fixitlab 2>/dev/null | sed '/^$/d' | wc -l | tr -d ' ')
[ "${PV_COUNT:-0}" -ge 2 ] || { echo "FAIL: add second disk to VG (pvcreate + vgextend)"; FAILED=1; }
SIZE=$(lvs --noheadings -o lv_size --units m --nosuffix fixitlab/datalv 2>/dev/null | tr -d ' ')
[ -n "$SIZE" ] && [ "${SIZE%%.*}" -ge 450 ] || { echo "FAIL: extend datalv to use new PV space (need >=450M)"; FAILED=1; }
mountpoint -q /data || mount /dev/fixitlab/datalv /data 2>/dev/null || mount /data 2>/dev/null || true
AVAIL=$(df -BM /data 2>/dev/null | tail -1 | awk '{print $4}' | tr -d M)
[ "${AVAIL:-0}" -ge 80 ] || { echo "FAIL: grow XFS on /data after lvextend (xfs_growfs)"; FAILED=1; }
[ $FAILED -eq 0 ] && echo PASS && exit 0
exit 1
