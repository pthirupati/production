#!/bin/bash
set -e
faillock --user lockeduser --reset 2>/dev/null || true
passwd -u lockeduser 2>/dev/null || true
