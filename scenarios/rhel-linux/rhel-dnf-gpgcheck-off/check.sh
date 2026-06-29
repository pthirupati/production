#!/bin/bash
firewall-cmd --state | grep -q 'running'
exit 0
