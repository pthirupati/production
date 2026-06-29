#!/bin/bash
pg_isready | grep -q 'accepting connections'
exit 0
