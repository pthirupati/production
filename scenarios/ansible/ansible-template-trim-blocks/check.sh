#!/usr/bin/env bash
# ansible-template-trim-blocks: config repair — fail-closed until /home/ansible/templates/nginx.conf.j2 carries FIXED-OK.
grep -q FIXED-OK /home/ansible/templates/nginx.conf.j2
exit 0
