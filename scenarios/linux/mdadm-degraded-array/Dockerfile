FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y mdadm e2fsprogs util-linux vim nano less procps python3 && apt-get clean && rm -rf /var/lib/apt/lists/*
COPY systemctl.py /usr/local/bin/systemctl
COPY service.sh /usr/local/bin/service
RUN chmod +x /usr/local/bin/systemctl /usr/local/bin/service
RUN mkdir -p /opt/fixitlab

COPY check.sh /opt/fixitlab/check.sh
COPY setup.sh /opt/fixitlab/setup.sh
RUN chmod +x /opt/fixitlab/setup.sh
RUN chmod +x /opt/fixitlab/check.sh
CMD ["/bin/bash"]
