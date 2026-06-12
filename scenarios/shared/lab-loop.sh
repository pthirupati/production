#!/bin/bash
# Shared loop-back helpers for FixitLab storage labs.
# Source from setup/fix scripts: . /opt/fixitlab/lab-loop.sh

fixitlab_backing_dir() {
  mkdir -p /opt/fixitlab/backing
}

fixitlab_loop_init() {
  modprobe loop 2>/dev/null || true
  modprobe dm-mod 2>/dev/null || modprobe dm_mod 2>/dev/null || true
  modprobe dm-mirror 2>/dev/null || modprobe dm_mirror 2>/dev/null || true
  modprobe dm-snapshot 2>/dev/null || modprobe dm_snapshot 2>/dev/null || true
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

# Attach img to a loop device with partition scanning enabled.
fixitlab_loop_attach() {
  local img="$1"
  local size="${2:-64M}"
  fixitlab_loop_init
  fixitlab_ensure_image "$img" "$size"
  local dev
  dev=$(losetup -j "$img" 2>/dev/null | cut -d: -f1 | head -1)
  if [ -n "$dev" ] && [ -b "$dev" ]; then
    losetup -P "$dev" "$img" 2>/dev/null || losetup --partscan "$dev" 2>/dev/null || true
    echo "$dev"
    return 0
  fi
  dev=$(losetup --find --show --partscan "$img" 2>/dev/null \
    || losetup -f -P --show "$img" 2>/dev/null \
    || losetup --find --show "$img" 2>/dev/null \
    || losetup -f --show "$img" 2>/dev/null || true)
  if [ -z "$dev" ] || [ ! -b "$dev" ]; then
    fixitlab_loop_detach_image "$img"
    dev=$(losetup --find --show --partscan "$img" 2>/dev/null || losetup -f -P --show "$img")
  fi
  [ -n "$dev" ] && [ -b "$dev" ] || { echo "losetup failed for $img" >&2; return 1; }
  echo "$dev"
}

# Wait for loop partition node (loop8p1) after parted.
fixitlab_loop_partdev() {
  local loop="$1"
  local partnum="${2:-1}"
  local p="${loop}p${partnum}"
  partprobe "$loop" 2>/dev/null || true
  blockdev --rereadpt "$loop" 2>/dev/null || true
  losetup -P "$loop" 2>/dev/null || true
  for _ in $(seq 1 30); do
    if [ -b "$p" ]; then
      echo "$p"
      return 0
    fi
    partx -u "$loop" 2>/dev/null || true
    sleep 0.2
  done
  echo "partition $p missing for $loop" >&2
  return 1
}

# Wait for an LVM logical volume block device.
fixitlab_lvm_wait_lv() {
  local lv="$1"
  local alt="${2:-}"
  for _ in $(seq 1 30); do
    vgchange -ay fixitlab 2>/dev/null || true
    dmsetup mknodes 2>/dev/null || true
    udevadm settle 2>/dev/null || true
    [ -b "$lv" ] && return 0
    if [ -n "$alt" ] && [ -b "$alt" ]; then
      return 0
    fi
    sleep 1
  done
  return 1
}

fixitlab_lvm_teardown() {
  vgchange -an fixitlab 2>/dev/null || true
  vgremove -ff fixitlab 2>/dev/null || true
}

fixitlab_lvm_lv_size_m() {
  lvs --noheadings -o lv_size --units m --nosuffix fixitlab/datalv 2>/dev/null \
    | tr -d ' ' | cut -d. -f1
}

fixitlab_mdadm_cleanup() {
  for md in /dev/md*; do
    [ -b "$md" ] || continue
    mdadm --stop "$md" 2>/dev/null || true
  done
  mdadm --stop --scan 2>/dev/null || true
}

# Release loop devices and LVM/MD state before container teardown (host-visible in privileged labs).
fixitlab_loop_cleanup() {
  fixitlab_loop_init
  fixitlab_mdadm_cleanup
  vgchange -an fixitlab 2>/dev/null || true
  for img in /opt/fixitlab/backing/*.img /var/*.img; do
    [ -f "$img" ] || continue
    fixitlab_loop_detach_image "$img"
  done
  losetup -D 2>/dev/null || true
}
