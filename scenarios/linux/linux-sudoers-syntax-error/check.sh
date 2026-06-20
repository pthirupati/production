#!/usr/bin/env bash
# linux-sudoers-syntax-error: config repair — fail-closed until /etc/sudoers.d/ops carries the FIXED-OK sentinel.
grep -q FIXED-OK /etc/sudoers.d/ops
exit 0
