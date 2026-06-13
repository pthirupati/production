FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y openssh-client rsync vim nano sudo && apt-get clean && rm -rf /var/lib/apt/lists/*
RUN useradd -m -s /bin/bash fixitlab && echo 'fixitlab ALL=(ALL) NOPASSWD:ALL' >> /etc/sudoers
RUN mkdir -p /var/www/app && echo '<html>app</html>' > /var/www/app/index.html
RUN mkdir -p /home/fixitlab/.ssh && ssh-keygen -t rsa -N "" -f /home/fixitlab/.ssh/id_rsa -q && chown -R fixitlab:fixitlab /home/fixitlab
COPY check.sh /opt/fixitlab/check.sh
RUN chmod +x /opt/fixitlab/check.sh
USER fixitlab
WORKDIR /home/fixitlab
CMD ["/bin/bash", "-c", "exec /bin/bash"]
