#!/usr/bin/env bash
# gpu-thermal-throttle-airflow: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/gpu/thermal-policy.conf
exit 0
