#!/bin/bash
FAILED=0
# Old PV should have zero used extents after pvmove
USED=$(pvs --noheadings -o pv_used --units m --nosuffix 2>/dev/null | head -1 | tr -d ' ')
[ -z "$USED" ] || [ "${USED%%.*}" -le 4 ] || { echo "FAIL: pvmove data off old PV first (pv_used should be ~0)"; FAILED=1; }
mountpoint -q /data || mount /data 2>/dev/null || true
[ -f /data/important.db ] || { echo "FAIL: /data must remain mounted with data intact"; FAILED=1; }
vgdisplay fixitlab 2>/dev/null | grep -q 'PV Name' && echo "OK: VG healthy"
[ $FAILED -eq 0 ] && echo PASS && exit 0
exit 1
