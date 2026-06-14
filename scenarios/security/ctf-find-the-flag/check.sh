#!/bin/bash
FLAG=$(cat /tmp/flag.txt 2>/dev/null | tr -d '[:space:]')
if [ "$FLAG" = "FIXITLAB{hidden_in_var_backups}" ]; then
  echo "OK: Flag captured!"
  exit 0
fi
echo "FAIL: Write the correct flag to /tmp/flag.txt"
exit 1
