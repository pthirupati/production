#!/bin/bash
set -e
sed -i '/192\.0\.2\.99/d' /etc/fstab
