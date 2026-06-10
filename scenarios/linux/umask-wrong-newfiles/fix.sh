#!/bin/bash
set -e
echo 'umask 022' > /etc/profile.d/99-bad-umask.sh
chmod 644 /etc/profile.d/99-bad-umask.sh
