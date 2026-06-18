#!/bin/bash
# Check that OSPF neighbor has reached Full state
OSPF_FULL=$(vtysh -c 'show ip ospf neighbor' 2>/dev/null | grep -c 'Full')
if [ "$OSPF_FULL" -gt 0 ]; then
  echo "OK: OSPF neighbor adjacency reached Full state"
  exit 0
fi
OSPF_STATE=$(vtysh -c 'show ip ospf neighbor' 2>/dev/null | grep -oE 'ExStart|Exchange|Loading' | head -1)
if [ "$OSPF_STATE" = "ExStart" ]; then
  echo "FAIL: OSPF neighbor still stuck in ExStart — check MTU mismatch on connected interfaces"
  exit 1
fi
echo "FAIL: OSPF neighbor not in Full state — current state: ${OSPF_STATE:-unknown}"
exit 1
