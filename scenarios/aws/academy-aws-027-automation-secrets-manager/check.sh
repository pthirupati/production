#!/usr/bin/env bash
systemctl is-failed --quiet 2>/dev/null; test $? -ne 0
exit 0
