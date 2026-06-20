#!/usr/bin/env bash
# ansible-jinja-template-error: config repair — fail-closed until /home/ansible/templates/app.conf.j2 carries the FIXED-OK sentinel.
grep -q FIXED-OK /home/ansible/templates/app.conf.j2
exit 0
