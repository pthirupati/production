#!/bin/bash
set -e
grep -v 'api\.internal\.wrong' /etc/hosts > /tmp/hosts.new
cat /tmp/hosts.new > /etc/hosts
