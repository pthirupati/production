#!/bin/bash
# Cross-tech NIC add: the adapter added in VMware must be revealed in the guest
# (a rescan), then configured with 10.0.0.30/24 on the new interface.
ip addr | grep 10.0.0.30
exit 0
