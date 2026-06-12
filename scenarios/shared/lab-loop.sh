#!/bin/bash
# Shared loop-back helpers for FixitLab storage labs.
# Source from setup/fix scripts: . /opt/fixitlab/lab-loop.sh

fixitlab_backing_dir() {
  mkdir -p /opt/fixitlab/backing
}

fixitlab_loop_init() {
  modprobe loop 2>/dev/null || true
  modprobe dm-mod 2>/dev/null || true
  mkdir -p /dev/mapper /dev
  [ -e /dev/loop-control ] || mknod -m 0666 /dev/loop-control c 10 237 2>/dev/null || true
  dmsetup mknodes 2>/dev/null || true
}

# Ensure a sparse backing file exists (size like 64M, 128M).
fixitlab_ensure_image() {
  local img="$1"
  local size="${2:-64M}"
  fixitlab_backing_dir
  if [ ! -s "$img" ]; then
    truncate -s "$size" "$img" 2>/dev/null || dd if=/dev/zero of="$img" bs=1M count="${size%M}" status=none
    sync "$img" 2>/dev/null || sync
  fi
  [ -s "$img" ] || { echo "backing image missing: $img" >&2; return 1; }
}

# Detach any loop device already bound to img (same path).
fixitlab_loop_detach_image() {
  local img="$1"
  local loop
  while read -r loop; do
    [ -n "$loop" ] && losetup -d "$loop" 2>/dev/null || true
  done < <(losetup -j "$img" 2>/dev/null | cut -d: -f1)
}

# Attach img to a loop device; reuse an existing attachment when present.
fixitlab_loop_attach() {
  local img="$1"
  local size="${2:-64M}"
  fixitlab_loop_init
  fixitlab_ensure_image "$img" "$size"
  local dev
  dev=$(losetup -j "$img" 2>/dev/null | cut -d: -f1 | head -1)
  if [ -n "$dev" ] && [ -b "$dev" ]; then
    echo "$dev"
    return 0
  fi
  dev=$(losetup --find --show "$img" 2>/dev/null || losetup -f --show "$img" 2>/dev/null || true)
  if [ -z "$dev" ] || [ ! -b "$dev" ]; then
    fixitlab_loop_detach_image "$img"
    dev=$(losetup --find --show "$img" 2>/dev/null || losetup -f --show "$img")
  fi
  [ -n "$dev" ] && [ -b "$dev" ] || { echo "losetup failed for $img" >&2; return 1; }
  echo "$dev"
}

# Release loop devices and LVM state before container teardown (host-visible in privileged labs).
fixitlab_loop_cleanup() {
  fixitlab_loop_init
  vgchange -an fixitlab 2>/dev/null || true
  for img in /opt/fixitlab/backing/*.img /var/*.img; do
    [ -f "$img" ] || continue
    fixitlab_loop_detach_image "$img"
  done
  losetup -D 2>/dev/null || true
}
