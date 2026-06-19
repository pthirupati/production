#!/bin/bash
systemctl is-active docker
docker ps | grep -q Up
exit 0
