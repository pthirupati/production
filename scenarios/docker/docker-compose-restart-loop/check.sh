#!/bin/bash
docker ps --format '{{.Status}}' | grep -q Up | grep -q 'Up'
exit 0
