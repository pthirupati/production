#!/bin/bash
set -e
ip route replace 10.50.0.0/24 via 172.16.0.1
