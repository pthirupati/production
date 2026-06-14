FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y vim nano less python3 curl findutils && apt-get clean && rm -rf /var/lib/apt/lists/*
COPY systemctl.py /usr/local/bin/systemctl
COPY service.sh /usr/local/bin/service
RUN chmod +x /usr/local/bin/systemctl /usr/local/bin/service
RUN mkdir -p /opt/fixitlab /var/backups/.secret
RUN echo 'FIXITLAB{hidden_in_var_backups}' > /var/backups/.secret/flag.txt && chmod 600 /var/backups/.secret/flag.txt
COPY check.sh /opt/fixitlab/check.sh
RUN chmod +x /opt/fixitlab/check.sh
CMD ["/bin/bash"]
