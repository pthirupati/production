#!/bin/bash
set -e
faillock --user lockeduser --reset 2>/dev/null || true
usermod -U lockeduser 2>/dev/null || passwd -u lockeduser 2>/dev/null || true
