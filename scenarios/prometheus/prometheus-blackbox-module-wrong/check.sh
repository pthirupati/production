#!/bin/bash
HTTP=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:9090/-/healthy 2>/dev/null)
test "$HTTP" = "200"
exit 0
