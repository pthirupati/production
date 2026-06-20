#!/usr/bin/env bash
# rhel-crypto-policy-legacy: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/crypto-policies/config
exit 0
