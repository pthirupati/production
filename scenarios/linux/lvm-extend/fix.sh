#!/bin/bash
set -e
lvextend -y -L 350M /dev/fixitlab/datalv 2>/dev/null || lvextend -y -l +100%FREE /dev/fixitlab/datalv 2>/dev/null || true
mountpoint -q /data || mount /data 2>/dev/null || true
xfs_growfs /data 2>/dev/null || true
resize2fs /dev/fixitlab/datalv 2>/dev/null || true
