#!/bin/bash
mount -o remount,noexec /tmp 2>/dev/null || mount --bind /tmp /tmp && mount -o remount,noexec,bind /tmp
echo "/tmp is noexec"

