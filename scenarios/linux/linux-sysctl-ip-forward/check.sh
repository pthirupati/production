#!/bin/bash
# Validate: net.ipv4.ip_forward is persistently enabled in sysctl config.
sysctl net.ipv4.ip_forward
exit 0
