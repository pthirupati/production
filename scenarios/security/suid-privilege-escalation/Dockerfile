FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y vim nano less python3 curl && apt-get clean && rm -rf /var/lib/apt/lists/*
COPY systemctl.py /usr/local/bin/systemctl
COPY service.sh /usr/local/bin/service
RUN chmod +x /usr/local/bin/systemctl /usr/local/bin/service
RUN useradd -m ctf && mkdir -p /opt/fixitlab /root
RUN echo 'FIXITLAB{suid_readflag_pwned}' > /root/flag.txt && chmod 600 /root/flag.txt
RUN printf '#!/bin/bash\nif [ "$1" = "-r" ] && [ -n "$2" ]; then cat "$2"; exit $?; fi\necho "Usage: readflag -r <file>" >&2; exit 1\n' > /usr/local/bin/readflag && chmod 4755 /usr/local/bin/readflag
COPY check.sh /opt/fixitlab/check.sh
RUN chmod +x /opt/fixitlab/check.sh
USER ctf
WORKDIR /home/ctf
CMD ["/bin/bash"]
