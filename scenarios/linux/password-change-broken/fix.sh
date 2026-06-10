#!/bin/bash
set -e
sed -i 's/pam_unixx\.so/pam_unix.so/g' /etc/pam.d/common-password
passwd -u devuser 2>/dev/null || true
