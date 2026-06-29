#!/bin/bash
nvidia-smi | grep -q 'NVIDIA-SMI'
exit 0
