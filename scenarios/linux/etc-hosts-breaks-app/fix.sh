#!/bin/bash
set -e
sed -i '/api\.internal\.wrong/d' /etc/hosts
