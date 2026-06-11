#!/bin/bash
set -e
[ -x /opt/fixitlab/setup.sh ] && bash /opt/fixitlab/setup.sh 2>/dev/null || true
lvextend -y -L 350M /dev/fixitlab/datalv
mountpoint -q /data || mount /dev/fixitlab/datalv /data
xfs_growfs /data 2>/dev/null || resize2fs /dev/fixitlab/datalv 2>/dev/null || true
