#!/bin/bash
set -e
sed -i '/^hosts:/d' /etc/nsswitch.conf
echo 'hosts: files dns' >> /etc/nsswitch.conf
sed -i 's/myhostname//g' /etc/nsswitch.conf
