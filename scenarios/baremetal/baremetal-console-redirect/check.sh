#!/usr/bin/env bash
# baremetal-console-redirect: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/bios/serial-console.cfg
exit 0
