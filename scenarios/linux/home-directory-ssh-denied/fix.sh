#!/bin/bash
set -e
chattr -i /home/ops 2>/dev/null || true
chmod 755 /home/ops
chown ops:ops /home/ops 2>/dev/null || true
