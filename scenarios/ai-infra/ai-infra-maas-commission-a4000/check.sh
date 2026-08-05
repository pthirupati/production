#!/usr/bin/env bash
grep -q FIXED-OK /opt/fixitlab/academy/ai-infra-maas-commission-a4000.conf
nvidia-smi -L | grep -qi 'A4000'
