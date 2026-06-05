#!/bin/bash
! grep -q 'api.internal.wrong' /etc/hosts && echo PASS && exit 0
echo FAIL: remove or fix wrong api.internal entry in /etc/hosts
exit 1
