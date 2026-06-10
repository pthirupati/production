#!/bin/bash
set -e
getent group devteam >/dev/null || groupadd devteam
id baduser >/dev/null 2>&1 && usermod -g devteam baduser || true
