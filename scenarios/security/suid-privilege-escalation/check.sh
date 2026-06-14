#!/bin/bash
FLAG=$(cat /tmp/flag.txt 2>/dev/null | tr -d '[:space:]')
if [ "$FLAG" = "FIXITLAB{suid_readflag_pwned}" ]; then
  echo "OK: Privilege escalation successful"
  exit 0
fi
echo "FAIL: Write the flag from /root/flag.txt to /tmp/flag.txt"
exit 1
