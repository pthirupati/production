#!/bin/bash
grep '/mnt/nfs' /etc/fstab | grep -qE 'nobootwait|nofail' && echo PASS && exit 0
! grep -q '192.0.2.99' /etc/fstab && echo PASS && exit 0
echo FAIL: comment out bad NFS line or add nfs nobootwait,nofail,soft,timeo=5
exit 1
