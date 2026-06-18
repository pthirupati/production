#!/usr/bin/env bash
# Check: Kinesis stream has more than 1 shard (scaled up from default).
set -euo pipefail

STREAM="${KINESIS_STREAM_NAME:-lab-stream}"

SHARD_COUNT=$(aws kinesis describe-stream-summary \
  --stream-name "$STREAM" \
  --query 'StreamDescriptionSummary.OpenShardCount' \
  --output text 2>/dev/null || echo "0")

if [[ "$SHARD_COUNT" -le 1 ]]; then
  echo "FAIL: Stream '$STREAM' still has $SHARD_COUNT shard(s). Expected > 1 to handle consumer lag."
  exit 1
fi

echo "PASS: Stream '$STREAM' has $SHARD_COUNT shards (scaled up successfully)."
exit 0
