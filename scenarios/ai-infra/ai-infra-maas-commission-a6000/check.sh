#!/usr/bin/env bash
grep -q FIXED-OK /opt/fixitlab/academy/ai-infra-maas-commission-a6000.conf
nvidia-smi -L | grep -qiE '6000 Ada|RTX 6000'
