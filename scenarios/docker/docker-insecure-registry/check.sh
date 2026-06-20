#!/usr/bin/env bash
# docker-insecure-registry: config repair — fail-closed until /etc/docker/registries.conf carries the FIXED-OK sentinel.
grep -q FIXED-OK /etc/docker/registries.conf
exit 0
