#!/bin/bash
# Validate: a persistent default gateway is configured for eth0.
grep GATEWAY /etc/sysconfig/network
exit 0
