#!/bin/bash
umount /data 2>/dev/null || true
# Simulate dirty filesystem
tune2fs -c 1 /data.img 2>/dev/null || true

