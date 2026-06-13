FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y openssh-client openssh-server vim nano less procps sudo && apt-get clean && rm -rf /var/lib/apt/lists/*
RUN mkdir -p /opt/fixitlab
RUN useradd -m -s /bin/bash fixitlab && echo 'fixitlab ALL=(ALL) NOPASSWD:ALL' >> /etc/sudoers
USER fixitlab
WORKDIR /home/fixitlab
RUN mkdir -p .ssh && ssh-keygen -t rsa -N "" -f .ssh/id_rsa -q
COPY check.sh /opt/fixitlab/check.sh
USER root
RUN chmod +x /opt/fixitlab/check.sh
CMD ["/bin/bash", "-c", "exec /bin/bash"]
