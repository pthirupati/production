#!/bin/bash
set -e
mapfile -t pvs_list < <(pvs --noheadings -o pv_name --separator ':' 2>/dev/null | tr -d ' ')
if [ "${#pvs_list[@]}" -ge 2 ]; then
  src="${pvs_list[0]}"
  dst="${pvs_list[1]}"
  pvmove "$src" "$dst" 2>/dev/null || pvmove "$src" 2>/dev/null || true
fi
mountpoint -q /data || mount /data 2>/dev/null || true
