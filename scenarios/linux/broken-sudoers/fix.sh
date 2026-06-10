#!/bin/bash
set -e
sed -i 's/ALLL/ALL/g' /etc/sudoers
id devops >/dev/null 2>&1 && (grep -q '^devops ' /etc/sudoers || echo 'devops ALL=(ALL:ALL) NOPASSWD: ALL' >> /etc/sudoers)
visudo -cf /etc/sudoers >/dev/null
