#!/bin/bash
set -e
mkdir -p /var/www/html /var/empty-overlay
echo '<h1>FixitLab Production</h1>' > /var/www/html/index.html
mount --bind /var/empty-overlay /var/www/html
echo "Bind mount hides real web root"

