#!/bin/bash
FAILED=0
OP=$(cat /etc/fixitlab-old-loop 2>/dev/null || true)
if [ -n "$OP" ] && pvs "$OP" >/dev/null 2>&1; then
  USED=$(pvs --noheadings -o pv_used --units m --nosuffix "$OP" 2>/dev/null | tr -d ' ')
  [ -z "$USED" ] || [ "${USED%%.*}" -le 4 ] || {
    echo "FAIL: pvmove data off old PV first (pv_used should be ~0)"
    FAILED=1
  }
else
  echo "OK: old PV removed from volume group"
fi
mountpoint -q /data || mount /dev/mapper/fixitlab-datalv /data 2>/dev/null || mount /dev/fixitlab/datalv /data 2>/dev/null || true
[ -f /data/important.db ] || { echo "FAIL: /data must remain mounted with data intact"; FAILED=1; }
vgdisplay fixitlab 2>/dev/null | grep -q 'PV Name' && echo "OK: VG healthy"
[ $FAILED -eq 0 ] && echo PASS && exit 0
exit 1
