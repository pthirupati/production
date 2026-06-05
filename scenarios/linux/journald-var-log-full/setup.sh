#!/bin/bash
set -e
mkdir -p /var/log/big
for i in $(seq 1 40); do dd if=/dev/zero of=/var/log/big/app$i.log bs=1M count=8 status=none; done
echo "/var/log filled with large app logs"

