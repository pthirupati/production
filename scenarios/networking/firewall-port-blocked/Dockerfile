FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y nginx iptables vim nano less procps python3 curl && \
    apt-get clean && rm -rf /var/lib/apt/lists/*
COPY systemctl.py /usr/local/bin/systemctl
COPY service.sh /usr/local/bin/service
RUN chmod +x /usr/local/bin/systemctl /usr/local/bin/service
RUN echo '<html><body><h1>App OK</h1></body></html>' > /var/www/html/index.html
RUN iptables -A INPUT -p tcp --dport 80 -j DROP
RUN mkdir -p /opt/fixitlab
COPY check.sh /opt/fixitlab/check.sh
RUN chmod +x /opt/fixitlab/check.sh
CMD ["/bin/bash", "-c", "nginx && exec /bin/bash"]
