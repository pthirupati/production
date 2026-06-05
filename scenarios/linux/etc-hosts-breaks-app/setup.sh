#!/bin/bash
# Apply broken /etc/hosts entry at container start (not during image build).
grep -q 'api.internal.wrong' /etc/hosts 2>/dev/null || \
  echo '127.0.0.1 api.internal.wrong' >> /etc/hosts
