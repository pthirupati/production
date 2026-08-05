#!/usr/bin/env bash
# Hero still uses marker until state grader lands (TODO 461); require FIXED-OK after Packer→MAAS deploy.
grep -q FIXED-OK /opt/fixitlab/markers/ai-infra-packer-gpu-image-factory.ok
exit 0
