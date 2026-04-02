# Scenario: "Fix the Broken Cron Job"
# Difficulty: Medium
# A backup cron job isn't running.

FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get install -y vim nano less cron procps python3 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install systemctl replacement for Docker containers
COPY systemctl.py /usr/local/bin/systemctl
COPY service.sh /usr/local/bin/service
RUN chmod +x /usr/local/bin/systemctl /usr/local/bin/service

# Create the backup script (NOT executable — that's the bug)
RUN echo '#!/bin/bash\ntar -czf /backups/backup-$(date +%Y%m%d).tar.gz /var/log 2>/dev/null' > /opt/backup.sh && \
    chmod 644 /opt/backup.sh && \
    mkdir -p /backups

# Copy validation script
RUN mkdir -p /opt/fixitlab
COPY check.sh /opt/fixitlab/check.sh
RUN chmod +x /opt/fixitlab/check.sh

# Add a valid cron entry but script is not executable (that's the bug)
# The user must: 1) chmod 755 /opt/backup.sh  2) verify cron is correct
RUN echo "0 2 * * * /opt/backup.sh" | crontab -

# Start cron daemon so the user can work with it
CMD ["/bin/bash", "-c", "cron && exec /bin/bash"]
