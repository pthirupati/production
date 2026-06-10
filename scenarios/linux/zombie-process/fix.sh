#!/bin/bash
set -e
pkill -f runaway.sh 2>/dev/null || true
pkill -f runaway 2>/dev/null || true
