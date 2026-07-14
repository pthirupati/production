#!/bin/bash
# Fail-closed grading — learner must apply the documented remediation in the lab.
grep -q FIXED-OK /opt/fixitlab/academy/gpu-amd-mi300-rocm-driver-mismatch.conf
