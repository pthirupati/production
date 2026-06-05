#!/bin/bash
# service wrapper script - delegates to systemctl
# Usage: service <name> <action>
if [ $# -lt 2 ]; then
    echo "Usage: service <service-name> {start|stop|restart|status}"
    exit 1
fi
SERVICE="$1"
ACTION="$2"
exec systemctl "$ACTION" "$SERVICE"
