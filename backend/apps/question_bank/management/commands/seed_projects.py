"""
Management command: seed_projects
Seeds starter end-to-end projects (2-tier Nginx, 3-tier architecture) for DevOps technologies.
Usage: python manage.py seed_projects
"""
from django.core.management.base import BaseCommand
from apps.question_bank.models import Technology, Project, ProjectTask


PROJECTS = [
    {
        "technology_slug": "linux",
        "title": "Deploy 2-Tier Nginx Web Application",
        "slug": "linux-2tier-nginx",
        "architecture_type": "2tier",
        "description": (
            "Build a production-ready 2-tier architecture with Nginx as the reverse proxy (tier 1) "
            "and a backend application server (tier 2). Follow each Jira ticket to configure, deploy, "
            "and secure the stack on a RHEL server."
        ),
        "objectives": [
            "Install and configure Nginx as a reverse proxy",
            "Deploy and run the backend application on port 8080",
            "Configure SSL/TLS with a self-signed certificate",
            "Set up firewall rules and test end-to-end connectivity",
        ],
        "difficulty": "intermediate",
        "estimated_hours": 3,
        "order": 1,
        "tasks": [
            {
                "jira_key": "NGINX-1",
                "title": "Install and start Nginx",
                "description": "Install the nginx package and ensure the service is running and enabled on boot.",
                "acceptance_criteria": "nginx is installed, running (`systemctl status nginx`), and enabled at boot.",
                "hint": "Use `dnf install nginx` then `systemctl enable --now nginx`. Verify with `curl localhost`.",
                "order": 1,
            },
            {
                "jira_key": "NGINX-2",
                "title": "Deploy backend application on port 8080",
                "description": (
                    "A simple Python Flask app is available at /opt/app/app.py. "
                    "Run it as a systemd service listening on port 8080."
                ),
                "acceptance_criteria": "`curl localhost:8080/health` returns HTTP 200 OK.",
                "hint": "Create /etc/systemd/system/webapp.service, enable and start it. Use `ss -tlnp` to verify port 8080.",
                "order": 2,
            },
            {
                "jira_key": "NGINX-3",
                "title": "Configure Nginx reverse proxy",
                "description": (
                    "Create an Nginx server block that proxies requests from port 80 to the backend on port 8080. "
                    "Place the config in /etc/nginx/conf.d/webapp.conf."
                ),
                "acceptance_criteria": "`curl localhost/health` proxies through Nginx to the backend.",
                "hint": "Use `proxy_pass http://127.0.0.1:8080;` inside a `location /` block. Test with `nginx -t` before reloading.",
                "order": 3,
            },
            {
                "jira_key": "NGINX-4",
                "title": "Configure firewall rules",
                "description": "Open HTTP (80) and HTTPS (443) ports in firewalld. Close port 8080 from external access.",
                "acceptance_criteria": "Ports 80 and 443 open; port 8080 not accessible externally. `firewall-cmd --list-all` shows correct rules.",
                "hint": "Use `firewall-cmd --permanent --add-service=http && firewall-cmd --reload`. For 8080: add a rich rule to block external access.",
                "order": 4,
            },
            {
                "jira_key": "NGINX-5",
                "title": "Enable SSL with self-signed certificate",
                "description": (
                    "Generate a self-signed certificate and configure Nginx to serve HTTPS on port 443. "
                    "Redirect HTTP traffic to HTTPS."
                ),
                "acceptance_criteria": "`curl -k https://localhost/health` returns 200. HTTP redirects to HTTPS.",
                "hint": "Use `openssl req -x509 -newkey rsa:4096 -keyout /etc/nginx/ssl/key.pem -out /etc/nginx/ssl/cert.pem -days 365 -nodes`. Update nginx.conf with ssl_certificate paths.",
                "order": 5,
            },
        ],
    },
    {
        "technology_slug": "linux",
        "title": "Build 3-Tier Architecture: LB + App + Database",
        "slug": "linux-3tier-lb-app-db",
        "architecture_type": "3tier",
        "description": (
            "Implement a full 3-tier architecture: Nginx load balancer (tier 1), two application server instances (tier 2), "
            "and a PostgreSQL database (tier 3). Follow Jira tickets to wire up each layer and verify end-to-end traffic flow."
        ),
        "objectives": [
            "Configure Nginx as an upstream load balancer across two app instances",
            "Deploy two app server instances with connection to a shared database",
            "Set up PostgreSQL, create a database, and configure remote access",
            "Implement health checks and verify traffic distribution",
        ],
        "difficulty": "advanced",
        "estimated_hours": 6,
        "order": 2,
        "tasks": [
            {
                "jira_key": "3TIER-1",
                "title": "Install and configure PostgreSQL",
                "description": (
                    "Install PostgreSQL 15, create a database called `appdb`, and a user `appuser` "
                    "with password `apppass`. Allow connections from localhost."
                ),
                "acceptance_criteria": "`psql -U appuser -d appdb -c 'SELECT 1'` succeeds.",
                "hint": "Use `dnf install postgresql-server`, then `postgresql-setup --initdb`, start the service. Use `psql -U postgres` to create DB and user.",
                "order": 1,
            },
            {
                "jira_key": "3TIER-2",
                "title": "Deploy App Instance 1 (port 8081)",
                "description": "Run the first application server instance on port 8081, connected to the PostgreSQL database.",
                "acceptance_criteria": "`curl localhost:8081/health` returns 200 with `{\"db\": \"connected\"}`.",
                "hint": "Set DB_HOST=localhost, DB_PORT=5432, PORT=8081 in the systemd unit's Environment block.",
                "order": 2,
            },
            {
                "jira_key": "3TIER-3",
                "title": "Deploy App Instance 2 (port 8082)",
                "description": "Run the second application server instance on port 8082 with the same database connection.",
                "acceptance_criteria": "`curl localhost:8082/health` returns 200 with `{\"db\": \"connected\"}`.",
                "hint": "Copy the systemd unit for instance 1, change PORT to 8082, and reload daemon.",
                "order": 3,
            },
            {
                "jira_key": "3TIER-4",
                "title": "Configure Nginx upstream load balancer",
                "description": (
                    "Create an Nginx upstream block that round-robins between the two app instances on ports 8081 and 8082. "
                    "Expose the load balancer on port 80."
                ),
                "acceptance_criteria": "Repeated `curl localhost/health` alternates responses between instance 1 and instance 2.",
                "hint": "Use `upstream app_servers { server 127.0.0.1:8081; server 127.0.0.1:8082; }` and `proxy_pass http://app_servers;` in the server block.",
                "order": 4,
            },
            {
                "jira_key": "3TIER-5",
                "title": "Add health check endpoint and monitoring",
                "description": (
                    "Configure Nginx to remove unhealthy backends automatically. "
                    "Add `max_fails=3 fail_timeout=30s` to each upstream server directive and verify failover."
                ),
                "acceptance_criteria": "When one app instance is stopped, all traffic routes to the remaining instance without error.",
                "hint": "Update upstream block: `server 127.0.0.1:8081 max_fails=3 fail_timeout=30s;`. Then stop instance 1 and verify with `curl localhost/health`.",
                "order": 5,
            },
            {
                "jira_key": "3TIER-6",
                "title": "Validate end-to-end data flow",
                "description": (
                    "POST data through the load balancer, verify it is stored in PostgreSQL, "
                    "and can be retrieved via GET. Demonstrate the full 3-tier data path."
                ),
                "acceptance_criteria": "`curl -X POST localhost/data` stores a record; `curl localhost/data` returns it from the database.",
                "hint": "Use `psql -U appuser -d appdb -c 'SELECT * FROM requests;'` to verify storage. Check app logs if the POST fails.",
                "order": 6,
            },
        ],
    },
    {
        "technology_slug": "docker",
        "title": "Containerised 2-Tier Stack with Docker Compose",
        "slug": "docker-2tier-compose",
        "architecture_type": "2tier",
        "description": (
            "Use Docker Compose to build and run a 2-tier stack: an Nginx container serving static files "
            "and proxying to a backend API container. Follow Jira tickets to write Dockerfiles, compose file, "
            "networking, and volume mounts."
        ),
        "objectives": [
            "Write a Dockerfile for the backend API",
            "Configure Nginx container with a custom config",
            "Wire both services in docker-compose.yml with bridge networking",
            "Add volume mounts for config and data persistence",
        ],
        "difficulty": "intermediate",
        "estimated_hours": 4,
        "order": 1,
        "tasks": [
            {
                "jira_key": "DCK-1",
                "title": "Write Dockerfile for the backend API",
                "description": "Create /opt/project/backend/Dockerfile that builds the Python Flask app, exposes port 5000.",
                "acceptance_criteria": "`docker build -t myapp-backend .` succeeds and `docker run myapp-backend` serves on port 5000.",
                "hint": "Base image: `python:3.11-slim`. Copy requirements.txt, run pip install, copy app code, EXPOSE 5000, CMD [\"python\", \"app.py\"].",
                "order": 1,
            },
            {
                "jira_key": "DCK-2",
                "title": "Configure Nginx as reverse proxy container",
                "description": "Create /opt/project/nginx/nginx.conf that proxies / to the backend service (hostname: backend, port: 5000).",
                "acceptance_criteria": "`nginx -t` passes inside the container; proxy_pass points to http://backend:5000.",
                "hint": "Use the `nginx:alpine` base image. Mount your custom nginx.conf to /etc/nginx/conf.d/default.conf.",
                "order": 2,
            },
            {
                "jira_key": "DCK-3",
                "title": "Create docker-compose.yml",
                "description": (
                    "Write a docker-compose.yml with two services: `backend` (built from ./backend) "
                    "and `nginx` (image: nginx:alpine, depends_on: backend). Use a custom bridge network."
                ),
                "acceptance_criteria": "`docker compose up -d` starts both containers. `docker compose ps` shows both healthy.",
                "hint": "Define a `networks: app-net: driver: bridge` section and add `networks: [app-net]` to each service.",
                "order": 3,
            },
            {
                "jira_key": "DCK-4",
                "title": "Add volume for persistent data",
                "description": "Mount a named Docker volume to /data inside the backend container for SQLite persistence.",
                "acceptance_criteria": "After `docker compose down && docker compose up -d`, data created previously is still accessible.",
                "hint": "Add `volumes: - app-data:/data` to the backend service and declare `volumes: app-data:` at the top level.",
                "order": 4,
            },
            {
                "jira_key": "DCK-5",
                "title": "Test end-to-end and verify logs",
                "description": "Curl through Nginx, verify the response comes from the backend. Check docker logs for both containers.",
                "acceptance_criteria": "`curl localhost:80/health` returns 200 proxied from backend. No ERROR lines in `docker compose logs`.",
                "hint": "Use `docker compose logs backend` and `docker compose logs nginx` to debug routing issues.",
                "order": 5,
            },
        ],
    },
    {
        "technology_slug": "kubernetes",
        "title": "Deploy Full App Stack on Kubernetes",
        "slug": "k8s-full-stack-deploy",
        "architecture_type": "3tier",
        "description": (
            "Deploy a complete application stack on Kubernetes: Deployment, Service, ConfigMap, PersistentVolumeClaim, "
            "and an Ingress rule. Each Jira ticket covers one Kubernetes object — follow them in order "
            "to build a production-grade deployment."
        ),
        "objectives": [
            "Create Deployment with resource limits and readiness probe",
            "Expose via ClusterIP Service and Ingress",
            "Mount config via ConfigMap and secrets via Secret",
            "Attach persistent storage with PVC",
        ],
        "difficulty": "advanced",
        "estimated_hours": 5,
        "order": 1,
        "tasks": [
            {
                "jira_key": "K8S-1",
                "title": "Create Namespace and ConfigMap",
                "description": "Create a namespace `myapp` and a ConfigMap `app-config` with APP_ENV=production and LOG_LEVEL=info.",
                "acceptance_criteria": "`kubectl get configmap app-config -n myapp -o yaml` shows both keys.",
                "hint": "Use `kubectl create namespace myapp` then write a ConfigMap YAML with `data:` section and apply with kubectl.",
                "order": 1,
            },
            {
                "jira_key": "K8S-2",
                "title": "Create Secret for DB credentials",
                "description": "Create a Secret `db-secret` in namespace `myapp` with keys DB_USER and DB_PASS.",
                "acceptance_criteria": "`kubectl get secret db-secret -n myapp` shows the secret exists (values base64-encoded).",
                "hint": "Use `kubectl create secret generic db-secret --from-literal=DB_USER=admin --from-literal=DB_PASS=secret -n myapp`.",
                "order": 2,
            },
            {
                "jira_key": "K8S-3",
                "title": "Create Deployment with resource limits",
                "description": (
                    "Deploy the app with 2 replicas, CPU limit 200m, memory limit 256Mi. "
                    "Mount the ConfigMap as environment variables and the Secret as env vars."
                ),
                "acceptance_criteria": "`kubectl get deploy -n myapp` shows 2/2 ready replicas.",
                "hint": "Use `envFrom: - configMapRef: name: app-config` and `- secretRef: name: db-secret` in the container spec.",
                "order": 3,
            },
            {
                "jira_key": "K8S-4",
                "title": "Create PersistentVolumeClaim",
                "description": "Create a 1Gi PVC named `app-storage` in namespace `myapp` and mount it at /data in the pod.",
                "acceptance_criteria": "`kubectl get pvc -n myapp` shows app-storage Bound. Data written to /data persists after pod restart.",
                "hint": "Add `volumes: - name: storage persistentVolumeClaim: claimName: app-storage` and a volumeMount to the container.",
                "order": 4,
            },
            {
                "jira_key": "K8S-5",
                "title": "Create Service and Ingress",
                "description": "Expose the Deployment with a ClusterIP Service on port 80, then add an Ingress rule for host `myapp.local`.",
                "acceptance_criteria": "`kubectl describe ingress -n myapp` shows the host and backend. `curl -H 'Host: myapp.local' <ingress-ip>` returns 200.",
                "hint": "Service targetPort should match the container's containerPort. Ingress class annotation: `kubernetes.io/ingress.class: nginx`.",
                "order": 5,
            },
        ],
    },
]


class Command(BaseCommand):
    help = "Seed starter end-to-end projects (2-tier Nginx, 3-tier, Kubernetes stack)"

    def handle(self, *args, **options):
        created_count = 0
        updated_count = 0
        for proj_data in PROJECTS:
            tech_slug = proj_data.pop("technology_slug")
            tasks_data = proj_data.pop("tasks")
            try:
                tech = Technology.objects.get(slug=tech_slug)
            except Technology.DoesNotExist:
                self.stderr.write(self.style.WARNING(f"Technology '{tech_slug}' not found — skipping project '{proj_data['title']}'"))
                continue

            project, created = Project.objects.update_or_create(
                slug=proj_data["slug"],
                defaults={**proj_data, "technology": tech},
            )

            for task_data in tasks_data:
                ProjectTask.objects.update_or_create(
                    project=project,
                    jira_key=task_data["jira_key"],
                    defaults=task_data,
                )

            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f"  Created: {project.title} [{tech.name}] ({len(tasks_data)} tasks)"))
            else:
                updated_count += 1
                self.stdout.write(f"  Updated: {project.title} [{tech.name}]")

        self.stdout.write(self.style.SUCCESS(
            f"\nProjects seeded: {created_count} created, {updated_count} updated."
        ))
