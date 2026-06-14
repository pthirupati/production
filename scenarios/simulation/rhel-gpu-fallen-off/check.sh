#!/bin/bash
nvidia-smi > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "FAIL: nvidia-smi still failing"
    exit 1
fi
echo "PASS"
exit 0
