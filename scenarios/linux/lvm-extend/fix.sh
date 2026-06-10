#!/bin/bash
set -e
mountpoint -q /data || mount /dev/fixitlab/datalv /data 2>/dev/null || mount /data 2>/dev/null || true
lvextend -y -L 350M /dev/fixitlab/datalv
xfs_growfs /data 2>/dev/null || resize2fs /dev/fixitlab/datalv 2>/dev/null || true
