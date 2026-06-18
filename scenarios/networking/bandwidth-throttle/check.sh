#!/bin/bash
# Check that the tc qdisc rate limit is corrected
QDISC=$(tc qdisc show dev eth0 2>/dev/null)
if echo "$QDISC" | grep -qE 'tbf.*rate.*1Mbit|tbf.*1mbit'; then
  echo "FAIL: tc qdisc still limiting eth0 to 1Mbit/s — remove and apply 100Mbit/s rule"
  exit 1
fi
if echo "$QDISC" | grep -qE 'tbf.*rate.*100Mbit|tbf.*100mbit'; then
  echo "OK: tc qdisc on eth0 correctly set to 100Mbit/s rate limit"
  exit 0
fi
# No tbf rule means default pfifo_fast (unlimited) — also acceptable
if echo "$QDISC" | grep -qE 'pfifo_fast|noqueue|fq_codel'; then
  echo "OK: traffic shaping removed from eth0 (using default qdisc)"
  exit 0
fi
echo "FAIL: tc qdisc configuration on eth0 is unclear — expected 100Mbit/s TBF or default qdisc"
exit 1
