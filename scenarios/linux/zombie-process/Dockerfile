# Scenario: "Kill the Zombie Process"
# Difficulty: Easy
# A runaway process is consuming excessive CPU.

FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get install -y vim nano less procps htop stress-ng python3 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install systemctl replacement for Docker containers
COPY systemctl.py /usr/local/bin/systemctl
COPY service.sh /usr/local/bin/service
RUN chmod +x /usr/local/bin/systemctl /usr/local/bin/service

# Create a script that wastes CPU
RUN echo '#!/bin/bash\nwhile true; do echo "working" > /dev/null; done' > /usr/local/bin/runaway.sh && \
    chmod +x /usr/local/bin/runaway.sh

# Copy validation script
RUN mkdir -p /opt/fixitlab
COPY check.sh /opt/fixitlab/check.sh
RUN chmod +x /opt/fixitlab/check.sh

# Start the runaway process in background, then drop to shell
CMD ["/bin/bash", "-c", "/usr/local/bin/runaway.sh & exec /bin/bash"]
