FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y vim nano less procps python3 util-linux && apt-get clean && rm -rf /var/lib/apt/lists/*
COPY systemctl.py /usr/local/bin/systemctl
COPY service.sh /usr/local/bin/service
RUN chmod +x /usr/local/bin/systemctl /usr/local/bin/service
RUN mkdir -p /opt/fixitlab
RUN mkdir -p /opt/install && echo '#!/bin/sh\necho installed' > /opt/install/run.sh && chmod +x /opt/install/run.sh
COPY check.sh /opt/fixitlab/check.sh
COPY setup.sh /opt/fixitlab/setup.sh
RUN chmod +x /opt/fixitlab/setup.sh
RUN chmod +x /opt/fixitlab/check.sh
CMD ["/bin/bash", "-c", "/opt/fixitlab/setup.sh 2>/dev/null; exec /bin/bash"]
