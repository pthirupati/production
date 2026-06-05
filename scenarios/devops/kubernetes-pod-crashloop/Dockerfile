# Scenario: Kubernetes Pod CrashLoop (simulated app deployment)
FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get install -y nginx vim nano less python3 curl && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

COPY systemctl.py /usr/local/bin/systemctl
COPY service.sh /usr/local/bin/service
RUN chmod +x /usr/local/bin/systemctl /usr/local/bin/service

RUN mkdir -p /opt/k8s /opt/fixitlab /var/www/html

# Simulated deployment manifest with wrong container port
RUN printf 'apiVersion: v1\nkind: Service\nmetadata:\n  name: webapp\nspec:\n  ports:\n  - port: 8080\n    targetPort: 8080\n---\napiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: webapp\nspec:\n  template:\n    spec:\n      containers:\n      - name: web\n        image: nginx:alpine\n        ports:\n        - containerPort: 80\n' > /opt/k8s/deployment.yaml

# Nginx listens on 80 but service expects 8080 — user must fix manifest
COPY check.sh /opt/fixitlab/check.sh
RUN chmod +x /opt/fixitlab/check.sh

RUN echo '<html><body><h1>Webapp OK</h1></body></html>' > /var/www/html/index.html

CMD ["/bin/bash", "-c", "nginx && exec /bin/bash"]
