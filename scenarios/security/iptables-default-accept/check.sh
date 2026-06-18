#!/bin/bash
# Check that default policy is not ACCEPT on INPUT
INPUT_POLICY=$(iptables -L INPUT -n 2>/dev/null | head -1 | grep -oE 'ACCEPT|DROP|REJECT')
if [ "$INPUT_POLICY" = "ACCEPT" ]; then
  echo "FAIL: iptables INPUT chain default policy is ACCEPT — change to DROP: iptables -P INPUT DROP"
  exit 1
fi
FORWARD_POLICY=$(iptables -L FORWARD -n 2>/dev/null | head -1 | grep -oE 'ACCEPT|DROP|REJECT')
if [ "$FORWARD_POLICY" = "ACCEPT" ]; then
  echo "FAIL: iptables FORWARD chain default policy is ACCEPT — change to DROP: iptables -P FORWARD DROP"
  exit 1
fi
# Check that SSH is still allowed (so we don't lock out the admin)
SSH_RULE=$(iptables -L INPUT -n 2>/dev/null | grep -E 'ACCEPT.*tcp.*22|dpt:22.*ACCEPT')
if [ -z "$SSH_RULE" ]; then
  # Check for RELATED/ESTABLISHED rule that would cover SSH sessions
  EST_RULE=$(iptables -L INPUT -n 2>/dev/null | grep -c 'ESTABLISHED.*RELATED\|RELATED.*ESTABLISHED')
  if [ "$EST_RULE" -eq 0 ]; then
    echo "FAIL: INPUT policy is DROP but no SSH ACCEPT rule found — you may lock yourself out!"
    exit 1
  fi
fi
echo "OK: iptables INPUT policy is DROP and FORWARD policy is ${FORWARD_POLICY:-DROP}"
exit 0
