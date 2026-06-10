#!/bin/bash
set -e
sed -i 's/ALLL/ALL/g' /etc/sudoers
sed -i '/^devops /d' /etc/sudoers
echo 'devops ALL=(ALL:ALL) NOPASSWD:ALL' >> /etc/sudoers
visudo -cf /etc/sudoers >/dev/null
