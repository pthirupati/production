#!/bin/bash
# Simulation validation: check DRS enabled and cluster balanced via API
curl -s -X GET "http://localhost:8000/api/vmware-sim/${SESSION_ID}/validate/" | grep -q "passed" && echo "PASS" && exit 0
echo "FAIL"; exit 1
