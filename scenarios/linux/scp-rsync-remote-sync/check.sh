#!/bin/bash
test -f /var/www/app/index.html && rsync -az -e "ssh -o StrictHostKeyChecking=no -o BatchMode=yes" /var/www/app/ syncuser@backup-server:/var/www/backup/ 2>/dev/null && \
ssh -o BatchMode=yes -o StrictHostKeyChecking=no syncuser@backup-server test -f /var/www/backup/index.html
