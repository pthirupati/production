# Scenario: "Disk Space Crisis"
# Difficulty: Medium
# A large log file is consuming all disk space. Find and fix it.

FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get install -y vim nano less procps coreutils python3 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install systemctl replacement for Docker containers
COPY systemctl.py /usr/local/bin/systemctl
COPY service.sh /usr/local/bin/service
RUN chmod +x /usr/local/bin/systemctl /usr/local/bin/service

# Create a very large log file (100MB) filling disk
RUN mkdir -p /var/log/webapp && \
    dd if=/dev/urandom bs=1M count=100 of=/var/log/webapp/application.log 2>/dev/null && \
    # Also hide one in a sneaky location
    mkdir -p /tmp/.hidden_cache && \
    dd if=/dev/urandom bs=1M count=50 of=/tmp/.hidden_cache/cache.dat 2>/dev/null

# Create a cron-like script that keeps growing the log
RUN echo '#!/bin/bash\nwhile true; do echo "$(date) ERROR: Something went wrong" >> /var/log/webapp/application.log; sleep 1; done' > /usr/local/bin/log_generator.sh && \
    chmod +x /usr/local/bin/log_generator.sh

# Copy validation script
RUN mkdir -p /opt/fixitlab
COPY check.sh /opt/fixitlab/check.sh
RUN chmod +x /opt/fixitlab/check.sh

# Start the log generator in background so user must find and kill it
CMD ["/bin/bash", "-c", "/usr/local/bin/log_generator.sh & exec /bin/bash"]
