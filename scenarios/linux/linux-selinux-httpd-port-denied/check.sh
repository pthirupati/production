#!/bin/bash
# Validate: SELinux still Enforcing, port 8080 labelled http_port_t, nginx running.
getenforce
semanage port -l | grep http_port_t
systemctl is-active nginx
exit 0
