FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y vim nano less procps python3 && apt-get clean && rm -rf /var/lib/apt/lists/*
COPY systemctl.py /usr/local/bin/systemctl
COPY service.sh /usr/local/bin/service
RUN chmod +x /usr/local/bin/systemctl /usr/local/bin/service
RUN mkdir -p /opt/fixitlab
RUN mkdir -p /opt/myapp && echo '#!/bin/bash\nwhile true; do echo running; sleep 5; done' > /opt/myapp/run.sh && chmod +x /opt/myapp/run.sh && echo -e '[Unit]\nDescription=MyApp\n[Service]\nType=simple\nExecStart=/opt/myapp/nope.sh\nRestart=on-failure\n[Install]\nWantedBy=multi-user.target' > /etc/systemd/system/myapp.service
COPY check.sh /opt/fixitlab/check.sh
RUN chmod +x /opt/fixitlab/check.sh
CMD ["/bin/bash", "-c", "exec /bin/bash"]
