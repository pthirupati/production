#!/bin/bash
/opt/fixitlab/precheck.sh
dnf update -y
reboot
uname -r
/opt/fixitlab/postcheck.sh
exit 0
