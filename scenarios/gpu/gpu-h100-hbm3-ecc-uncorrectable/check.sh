#!/bin/bash
# Fail-closed grading — learner must apply the documented remediation in the lab.
grep -q FIXED-OK /opt/fixitlab/academy/gpu-h100-hbm3-ecc-uncorrectable.conf
