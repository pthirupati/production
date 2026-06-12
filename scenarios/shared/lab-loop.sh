#!/bin/bash
# Shared loop-back helpers for FixitLab storage labs.
# Source from setup/fix scripts: . /opt/fixitlab/lab-loop.sh

fixitlab_backing_dir() {
  mkdir -p /opt/fixitlab/backing
}

# Ensure a sparse backing file exists (size like 64M, 128M).
fixitlab_ensure_image() {
  local img="$1"
  local size="${2:-64M}"
  fixitlab_backing_dir
  if [ ! -s "$img" ]; then
    truncate -s "$size" "$img" 2>/dev/null || dd if=/dev/zero of="$img" bs=1M count="${size%M}" status=none
  fi
  [ -s "$img" ] || { echo "backing image missing: $img" >&2; return 1; }
}

# Attach img to a loop device; reuse an existing attachment when present.
fixitlab_loop_attach() {
  local img="$1"
  local size="${2:-64M}"
  modprobe loop 2>/dev/null || true
  fixitlab_ensure_image "$img" "$size"
  local dev
  dev=$(losetup -j "$img" 2>/dev/null | cut -d: -f1 | head -1)
  if [ -n "$dev" ] && [ -b "$dev" ]; then
    echo "$dev"
    return 0
  fi
  dev=$(losetup --find --show "$img" 2>/dev/null || losetup -f --show "$img")
  [ -n "$dev" ] && [ -b "$dev" ] || { echo "losetup failed for $img" >&2; return 1; }
  echo "$dev"
}

fixitlab_loop_detach_all() {
  losetup -D 2>/dev/null || true
}
