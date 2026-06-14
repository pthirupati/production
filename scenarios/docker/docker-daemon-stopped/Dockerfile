FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get install -y docker.io curl vim nano less python3 procps iproute2 && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

COPY systemctl.py /usr/local/bin/systemctl
COPY service.sh /usr/local/bin/service
RUN chmod +x /usr/local/bin/systemctl /usr/local/bin/service

RUN mkdir -p /opt/fixitlab
COPY check.sh /opt/fixitlab/check.sh
RUN chmod +x /opt/fixitlab/check.sh

# Docker installed but service disabled / not started
RUN systemctl disable docker 2>/dev/null || true

CMD ["/bin/bash"]
