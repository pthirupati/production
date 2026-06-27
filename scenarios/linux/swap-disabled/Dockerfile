FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y vim nano less procps python3 && apt-get clean && rm -rf /var/lib/apt/lists/*
COPY systemctl.py /usr/local/bin/systemctl
COPY service.sh /usr/local/bin/service
RUN chmod +x /usr/local/bin/systemctl /usr/local/bin/service
RUN mkdir -p /opt/fixitlab
# mkswap is best-effort at build time: on hosts that already have an active
# /swapfile (in /proc/swaps) the kernel refuses to format the same path
# ("is mounted; will not make swapspace"). The lab is simulation-mode and the
# runtime fix.sh re-runs mkswap; check.sh only requires the 256MB file to exist,
# so a build-time mkswap failure must not break the image build.
RUN dd if=/dev/zero of=/swapfile bs=1M count=256 status=none && chmod 600 /swapfile && (mkswap /swapfile || echo "mkswap deferred to runtime (host swap collision)")
COPY check.sh /opt/fixitlab/check.sh
RUN chmod +x /opt/fixitlab/check.sh
CMD ["/bin/bash", "-c", "exec /bin/bash"]
