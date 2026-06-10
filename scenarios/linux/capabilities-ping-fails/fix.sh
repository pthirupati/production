#!/bin/bash
set -e
PING=$(command -v ping)
setcap cap_net_raw+ep "$PING"
