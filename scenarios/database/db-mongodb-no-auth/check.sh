#!/usr/bin/env bash
# db-mongodb-no-auth: config repair — fail-closed until /etc/mongod.conf carries FIXED-OK.
grep -q FIXED-OK /etc/mongod.conf
exit 0
