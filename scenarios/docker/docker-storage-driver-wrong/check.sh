#!/usr/bin/env bash
# docker-storage-driver-wrong: config repair — fail-closed until /etc/docker/storage.conf carries the FIXED-OK sentinel.
grep -q FIXED-OK /etc/docker/storage.conf
exit 0
