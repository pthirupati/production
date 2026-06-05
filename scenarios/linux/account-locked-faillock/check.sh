#!/bin/bash
passwd -S lockeduser 2>/dev/null | grep -q P && echo PASS && exit 0
faillock --user lockeduser 2>/dev/null | grep -q 'when' && { echo FAIL: faillock --user lockeduser --reset; exit 1; }
passwd -u lockeduser 2>/dev/null; passwd -S lockeduser | grep -q P && echo PASS && exit 0
echo FAIL: unlock with faillock --reset or passwd -u
exit 1
