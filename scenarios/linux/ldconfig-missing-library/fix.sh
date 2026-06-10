#!/bin/bash
set -e
echo '/usr/local/lib' > /etc/ld.so.conf.d/fixitlab.conf
ldconfig
