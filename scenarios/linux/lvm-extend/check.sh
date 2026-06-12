#!/bin/bash
FAILED=0
SIZE=$(lvs --noheadings -o lv_size --units m --nosuffix fixitlab/datalv 2>/dev/null | tr -d ' ')
if [ -z "$SIZE" ] || [ "${SIZE%%.*}" -lt 350 ]; then
    echo "FAIL: LV datalv should be extended to at least 350M (currently ${SIZE:-unknown}M)"
    FAILED=1
else
    echo "OK: LV size ${SIZE}M"
fi
mountpoint -q /data || mount /dev/mapper/fixitlab-datalv /data 2>/dev/null || mount /dev/fixitlab/datalv /data 2>/dev/null || mount /data 2>/dev/null || true
if mountpoint -q /data; then
    AVAIL=$(df -BM /data | tail -1 | awk '{print $4}' | tr -d M)
    if [ "${AVAIL:-0}" -lt 50 ]; then
        echo "FAIL: /data filesystem still too full after extend"
        FAILED=1
    else
        echo "OK: /data has ${AVAIL}M free"
    fi
else
    echo "FAIL: /data not mounted"
    FAILED=1
fi
[ $FAILED -eq 0 ] && echo "PASS: LVM extended successfully" && exit 0
exit 1
