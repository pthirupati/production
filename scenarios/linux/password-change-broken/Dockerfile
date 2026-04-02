# Scenario: "Password Change Broken"
# Difficulty: Easy
# A user "devuser" cannot change their password due to
# a corrupted PAM configuration and a locked account.

FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get install -y passwd login vim nano less procps iproute2 net-tools python3 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install systemctl replacement for Docker containers
COPY systemctl.py /usr/local/bin/systemctl
COPY service.sh /usr/local/bin/service
RUN chmod +x /usr/local/bin/systemctl /usr/local/bin/service

# Create validation directory
RUN mkdir -p /opt/fixitlab

# Copy the validation script into the container
COPY check.sh /opt/fixitlab/check.sh
RUN chmod +x /opt/fixitlab/check.sh

# Create a test user with a known password
RUN useradd -m -s /bin/bash devuser && \
    echo "devuser:FixitLab2024" | chpasswd

# ── Introduce the breaks ──

# Break 1: Corrupt PAM — typo in pam_unix module name
RUN sed -i 's/pam_unix\.so/pam_unixx.so/g' /etc/pam.d/common-password

# Break 2: Lock the user account (adds '!' prefix to shadow hash)
RUN passwd -l devuser

# Drop to a shell (user connects to this container as root)
CMD ["/bin/bash"]
