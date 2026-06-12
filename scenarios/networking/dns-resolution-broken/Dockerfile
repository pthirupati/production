# Scenario: "DNS Resolution Broken"
# Difficulty: Medium
# The server cannot resolve domain names.

FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get install -y vim nano less dnsutils net-tools iputils-ping curl procps python3 dnsmasq && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install systemctl replacement for Docker containers
COPY systemctl.py /usr/local/bin/systemctl
COPY service.sh /usr/local/bin/service
RUN chmod +x /usr/local/bin/systemctl /usr/local/bin/service

# Copy validation script
RUN mkdir -p /opt/fixitlab
COPY check.sh /opt/fixitlab/check.sh
COPY setup.sh /opt/fixitlab/setup.sh
RUN chmod +x /opt/fixitlab/check.sh /opt/fixitlab/setup.sh

CMD ["/bin/bash"]
