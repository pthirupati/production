# Scenario: "SSH Configuration Lockout"
# Difficulty: Hard
# SSH daemon won't start because of multiple config issues.

FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get install -y openssh-server vim nano less net-tools procps python3 iproute2 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install systemctl replacement for Docker containers
COPY systemctl.py /usr/local/bin/systemctl
COPY service.sh /usr/local/bin/service
RUN chmod +x /usr/local/bin/systemctl /usr/local/bin/service

# Break SSH in multiple ways
RUN mkdir -p /run/sshd && \
    # Wrong port + invalid option + bad permissions on host key
    sed -i 's/#Port 22/Port 2222/' /etc/ssh/sshd_config && \
    echo "InvalidOption yes" >> /etc/ssh/sshd_config && \
    chmod 777 /etc/ssh/ssh_host_rsa_key && \
    # Create a user that should be able to login
    useradd -m -s /bin/bash fixitlab && \
    echo "fixitlab:password123" | chpasswd

# Copy validation script
RUN mkdir -p /opt/fixitlab
COPY check.sh /opt/fixitlab/check.sh
RUN chmod +x /opt/fixitlab/check.sh

CMD ["/bin/bash"]
