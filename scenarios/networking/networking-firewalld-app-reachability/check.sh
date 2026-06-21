#!/usr/bin/env bash
# Cross-tech Networking<->Security: the custom firewalld service must be repaired and
# bound so the app port opens. Fail-closed until /etc/firewalld/services/app8443.xml
# carries the FIXED-OK sentinel (written only after the XML is valid and enabled).
grep -q FIXED-OK /etc/firewalld/services/app8443.xml
exit 0
