#!/bin/bash
# Fail-closed grading — learner must apply the documented remediation in the lab.
grep -q FIXED-OK /opt/fixitlab/academy/gpu-amd-smi-mi300x-missing.conf
