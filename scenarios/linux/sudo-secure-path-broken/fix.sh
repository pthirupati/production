#!/bin/bash
set -e
mkdir -p /etc/sudoers.d
echo 'Defaults secure_path="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"' > /etc/sudoers.d/99-bad-path
chmod 440 /etc/sudoers.d/99-bad-path
visudo -cf /etc/sudoers.d/99-bad-path >/dev/null
