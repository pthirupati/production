FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y openssh-client vim nano less procps python3 && apt-get clean && rm -rf /var/lib/apt/lists/*
COPY systemctl.py /usr/local/bin/systemctl
COPY service.sh /usr/local/bin/service
RUN chmod +x /usr/local/bin/systemctl /usr/local/bin/service
RUN mkdir -p /opt/fixitlab
RUN useradd -m dev && mkdir -p /home/dev/.ssh && echo 'ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQC test' > /home/dev/.ssh/authorized_keys && chmod 777 /home/dev/.ssh && chmod 644 /home/dev/.ssh/authorized_keys && chown -R dev:dev /home/dev/.ssh
COPY check.sh /opt/fixitlab/check.sh
RUN chmod +x /opt/fixitlab/check.sh
CMD ["/bin/bash", "-c", "exec /bin/bash"]
