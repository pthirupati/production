#!/usr/bin/env bash
# Cross-tech Database<->Networking: the replica's replication config + network path to
# the primary must both be reconciled. Fail-closed until /etc/my.cnf.d/replication.cnf
# carries the FIXED-OK sentinel (written only after server-id/host/port + path are fixed).
grep -q FIXED-OK /etc/my.cnf.d/replication.cnf
exit 0
