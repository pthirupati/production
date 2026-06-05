# Scenario: Broken CI/CD Pipeline Config
FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get install -y git vim nano less python3 python3-yaml curl && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

COPY systemctl.py /usr/local/bin/systemctl
COPY service.sh /usr/local/bin/service
RUN chmod +x /usr/local/bin/systemctl /usr/local/bin/service

RUN mkdir -p /opt/app /opt/fixitlab
WORKDIR /opt/app

# Broken GitLab CI config (invalid YAML indentation + wrong image tag)
RUN printf 'stages:\n  - build\n\nbuild_job:\n  stage: build\n image: node:18-alpinee\n  script:\n   - npm ci\n   - npm run build\n' > .gitlab-ci.yml

COPY check.sh /opt/fixitlab/check.sh
RUN chmod +x /opt/fixitlab/check.sh

CMD ["/bin/bash"]
