FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y openssl nginx vim nano less procps python3 && \
    apt-get clean && rm -rf /var/lib/apt/lists/*
COPY systemctl.py /usr/local/bin/systemctl
COPY service.sh /usr/local/bin/service
RUN chmod +x /usr/local/bin/systemctl /usr/local/bin/service
RUN mkdir -p /etc/nginx/ssl /opt/fixitlab && \
    openssl req -x509 -nodes -days 1 -newkey rsa:2048 \
      -keyout /etc/nginx/ssl/key.pem -out /etc/nginx/ssl/cert.pem \
      -subj "/CN=expired.local" && \
    echo 'server { listen 443 ssl; ssl_certificate /etc/nginx/ssl/cert.pem; ssl_certificate_key /etc/nginx/ssl/key.pem; location / { return 200 "ok"; } }' > /etc/nginx/sites-available/default
RUN apt-get update && apt-get install -y cron && apt-get clean && rm -rf /var/lib/apt/lists/*
COPY check.sh /opt/fixitlab/check.sh
# Pre-expired probe cert the grader feeds to the learner's expiry monitor.
COPY probe-expired.pem /opt/fixitlab/probe-expired.pem
RUN chmod +x /opt/fixitlab/check.sh
CMD ["/bin/bash"]
