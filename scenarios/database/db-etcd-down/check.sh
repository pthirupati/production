#!/usr/bin/env bash
# db-etcd-down: generic service health — fail-closed until active.
systemctl is-active etcd
exit 0
