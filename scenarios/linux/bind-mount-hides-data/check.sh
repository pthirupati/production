#!/bin/bash
[ -f /var/www/html/index.html ] && grep -q 'FixitLab Production' /var/www/html/index.html && echo PASS && exit 0
mount | grep -q '/var/www/html' && echo "FAIL: empty bind mount still covers /var/www/html — umount it" && exit 1
echo FAIL: umount /var/www/html bind mount so real site files are visible
exit 1
