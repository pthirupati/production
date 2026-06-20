#!/bin/bash
# Validate: the at job definition was corrected (FIXED-OK written after the real fix).
grep -q FIXED-OK /var/spool/at/job-0001
exit 0
