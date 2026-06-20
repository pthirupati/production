#!/usr/bin/env bash
# db-elasticsearch-down: generic service health — fail-closed until active.
systemctl is-active elasticsearch
exit 0
