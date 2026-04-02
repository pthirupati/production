# Scenario: "DNS Resolution Broken"
# Difficulty: Medium
# The server cannot resolve domain names.

FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get install -y vim nano less dnsutils net-tools iputils-ping curl procps python3 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install systemctl replacement for Docker containers
COPY systemctl.py /usr/local/bin/systemctl
COPY service.sh /usr/local/bin/service
RUN chmod +x /usr/local/bin/systemctl /usr/local/bin/service

# Copy validation script
RUN mkdir -p /opt/fixitlab
COPY check.sh /opt/fixitlab/check.sh
RUN chmod +x /opt/fixitlab/check.sh

# Break DNS: /etc/resolv.conf is mounted by Docker, so write at runtime
CMD ["/bin/bash", "-c", "echo 'nameserver 192.0.2.1' > /etc/resolv.conf && echo 'nameserver 198.51.100.1' >> /etc/resolv.conf && exec /bin/bash"]
