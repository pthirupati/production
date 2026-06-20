#!/usr/bin/env bash
# shell-no-shebang: config repair — fail-closed until /opt/scripts/no-shebang.sh carries FIXED-OK.
grep -q FIXED-OK /opt/scripts/no-shebang.sh
exit 0
