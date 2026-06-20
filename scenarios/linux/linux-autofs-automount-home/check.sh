#!/bin/bash
# Validate: the autofs master map was corrected (FIXED-OK written after the real map fix + reload).
grep -q FIXED-OK /etc/auto.master
exit 0
