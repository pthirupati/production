FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y vim nano less procps python3 libnss-myhostname2 2>/dev/null || true && apt-get clean && rm -rf /var/lib/apt/lists/*
COPY systemctl.py /usr/local/bin/systemctl
COPY service.sh /usr/local/bin/service
RUN chmod +x /usr/local/bin/systemctl /usr/local/bin/service
RUN mkdir -p /opt/fixitlab
RUN sed -i 's/^hosts:.*/hosts: files myhostname dns/' /etc/nsswitch.conf 2>/dev/null || echo 'hosts: files dns' > /etc/nsswitch.conf
COPY check.sh /opt/fixitlab/check.sh
RUN chmod +x /opt/fixitlab/check.sh
CMD ["/bin/bash", "-c", "exec /bin/bash"]
