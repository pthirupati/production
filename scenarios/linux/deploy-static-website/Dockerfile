# Scenario: "Fix the Broken Nginx Server"
# Difficulty: Easy
# The nginx config has a typo that prevents it from starting.

FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get install -y nginx curl vim nano less procps python3 iproute2 net-tools && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install systemctl replacement for Docker containers
COPY systemctl.py /usr/local/bin/systemctl
COPY service.sh /usr/local/bin/service
RUN chmod +x /usr/local/bin/systemctl /usr/local/bin/service

# Create validation directory
RUN mkdir -p /opt/fixitlab

# Copy the validation script into the container
COPY check.sh /opt/fixitlab/check.sh
RUN chmod +x /opt/fixitlab/check.sh

# Create a simple index page
RUN echo '<html><body><h1>FixitLab Works!</h1></body></html>' > /var/www/html/index.html

# Break nginx: introduce a typo in the config
# This MUST be after the index page creation and LAST before CMD

# Drop to a shell (user connects to this container)
CMD ["/bin/bash"]
