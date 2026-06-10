#!/bin/bash
set -e
chattr -i /home/dev/.ssh /home/dev/.ssh/authorized_keys 2>/dev/null || true
chmod 700 /home/dev/.ssh
chmod 600 /home/dev/.ssh/authorized_keys
chown -R dev:dev /home/dev/.ssh
