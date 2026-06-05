#!/bin/bash
mount | grep ' /data ' | grep -q rw && test -w /data/file.txt && echo PASS && exit 0
echo FAIL: remount /data read-write: mount -o remount,rw /data
exit 1
