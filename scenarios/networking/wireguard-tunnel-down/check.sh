#!/bin/bash
# Check that WireGuard peer config has been updated
CONF="/etc/wireguard/wg0.conf"
NEW_KEY_FILE="/etc/wireguard/new-peer-pubkey.txt"
if [ ! -f "$CONF" ]; then
  echo "FAIL: WireGuard config $CONF not found"
  exit 1
fi
# Check that new peer key is in config (if the new key file exists)
if [ -f "$NEW_KEY_FILE" ]; then
  NEW_KEY=$(cat "$NEW_KEY_FILE" | tr -d '[:space:]')
  if ! grep -q "$NEW_KEY" "$CONF"; then
    echo "FAIL: WireGuard peer public key not updated — copy the key from $NEW_KEY_FILE into $CONF"
    exit 1
  fi
fi
# Check that 10.10.0.0/16 is in AllowedIPs
if ! grep -q '10\.10\.0\.0/16' "$CONF"; then
  echo "FAIL: AllowedIPs in $CONF is missing 10.10.0.0/16 — add it to the [Peer] block"
  exit 1
fi
# Check that wg0 is up and has a recent handshake
HANDSHAKE=$(wg show wg0 latest-handshakes 2>/dev/null | awk '{print $2}' | head -1)
NOW=$(date +%s)
if [ -n "$HANDSHAKE" ] && [ "$HANDSHAKE" != "0" ]; then
  AGE=$((NOW - HANDSHAKE))
  if [ "$AGE" -lt 180 ]; then
    echo "OK: WireGuard peer config updated and handshake active (${AGE}s ago)"
    exit 0
  fi
fi
echo "FAIL: config looks correct but no recent handshake — restart tunnel: wg-quick down wg0 && wg-quick up wg0"
exit 1
