FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y vim nano less procps python3 && apt-get clean && rm -rf /var/lib/apt/lists/*
COPY systemctl.py /usr/local/bin/systemctl
COPY service.sh /usr/local/bin/service
RUN chmod +x /usr/local/bin/systemctl /usr/local/bin/service
RUN mkdir -p /opt/fixitlab
RUN mkdir -p /opt/app/bin && printf '#!/bin/bash\necho ok\n' > /opt/app/bin/real.sh && chmod +x /opt/app/bin/real.sh && ln -sf /opt/app/bin/wrong.sh /usr/local/bin/apptool
COPY check.sh /opt/fixitlab/check.sh
RUN chmod +x /opt/fixitlab/check.sh
CMD ["/bin/bash", "-c", "exec /bin/bash"]
