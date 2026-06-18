#!/bin/bash
# Check that container-ns has a veth interface with an IP and can reach the bridge
NS="container-ns"
# Verify namespace exists
if ! ip netns list 2>/dev/null | grep -q "$NS"; then
  echo "FAIL: network namespace '$NS' does not exist"
  exit 1
fi
# Check that a veth interface is present inside the namespace with an IP
NS_IP=$(ip netns exec "$NS" ip -4 addr show 2>/dev/null | grep 'inet ' | awk '{print $2}' | head -1)
if [ -z "$NS_IP" ]; then
  echo "FAIL: no IP address configured on any interface inside namespace '$NS'"
  exit 1
fi
# Check that the namespace has a default route or can reach the bridge
if ip netns exec "$NS" ip route show 2>/dev/null | grep -qE 'default|172\.16\.|192\.168\.'; then
  echo "OK: namespace '$NS' has IP ($NS_IP) and routing configured"
  exit 0
fi
echo "FAIL: namespace '$NS' has IP ($NS_IP) but no route to host bridge — check bridge attachment"
exit 1
