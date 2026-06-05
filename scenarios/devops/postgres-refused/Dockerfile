# Scenario: PostgreSQL Connection Refused
FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get install -y postgresql postgresql-contrib vim nano less procps python3 && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

COPY systemctl.py /usr/local/bin/systemctl
COPY service.sh /usr/local/bin/service
RUN chmod +x /usr/local/bin/systemctl /usr/local/bin/service

RUN mkdir -p /opt/fixitlab
COPY check.sh /opt/fixitlab/check.sh
RUN chmod +x /opt/fixitlab/check.sh

# Break postgres: wrong listen_addresses
RUN echo "listen_addresses = '127.0.0.1'" >> /etc/postgresql/14/main/postgresql.conf && \
    sed -i "s/#listen_addresses = 'localhost'/listen_addresses = '0.0.0.0'/" /etc/postgresql/14/main/postgresql.conf && \
    echo "listen_addresses = 'none'" >> /etc/postgresql/14/main/postgresql.conf

CMD ["/bin/bash"]
