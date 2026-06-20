#!/usr/bin/env bash
# win-scheduled-task-not-running: Windows validation — fail-closed until windows_fixed.
Get-Service Schedule
exit 0
