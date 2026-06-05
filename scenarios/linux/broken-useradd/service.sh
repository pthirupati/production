#!/bin/bash
if [ $# -lt 2 ]; then
    echo "Usage: service <service-name> {start|stop|restart|status}"
    exit 1
fi
exec systemctl "$2" "$1"
