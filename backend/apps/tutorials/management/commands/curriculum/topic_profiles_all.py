"""Complete topic profiles for all 60 catalog topics — no synthesized gaps."""

from __future__ import annotations

from .topic_profiles import TOPIC_PROFILES as _BASE

# Extended profiles for topics not in base or needing enrichment
EXTENDED_PROFILES: dict[str, dict] = {
    "AI Engineering": {
        "tagline": "ML, LLMs, RAG, agents, and MLOps from research to production",
        "architecture": "Data → features → train → register → deploy → monitor → retrain loop.",
        "concepts": {"mlops": "Version data, code, and models. CI/CD for training pipelines.", "rag": "Retrieve context chunks before LLM generation.", "agents": "Tool-use loops with guardrails and evals."},
        "commands": {"python": "python -m pip install -r requirements.txt && pytest"},
        "certs": "ML engineer certifications, FixitLab AI tracks",
    },
    "AWS": {
        "tagline": "Amazon Web Services cloud architecture and operations",
        "architecture": "Regions/AZs, VPC, IAM, EC2, S3, RDS, EKS — shared responsibility model.",
        "concepts": {"iam": "Users, roles, policies — least privilege.", "vpc": "Subnets, route tables, NACLs, security groups."},
        "commands": {"sts": "aws sts get-caller-identity", "s3": "aws s3 ls"},
        "certs": "AWS Solutions Architect, SysOps, DevOps Professional",
    },
    "Azure": {
        "tagline": "Microsoft Azure cloud platform",
        "architecture": "Subscriptions, resource groups, RBAC, VNets, AKS.",
        "concepts": {"rbac": "Role assignments at subscription/resource scope."},
        "certs": "AZ-104, AZ-305, AZ-400",
    },
    "GCP": {
        "tagline": "Google Cloud Platform services and GKE",
        "architecture": "Projects, VPC, GCE, GCS, Cloud SQL, GKE.",
        "certs": "Professional Cloud Architect, GKE",
    },
    "Backend": {
        "tagline": "Server-side APIs, databases, and distributed systems",
        "concepts": {"rest": "Resources, HTTP verbs, status codes, idempotency keys.", "auth": "JWT, OAuth2, mTLS for service-to-service."},
    },
    "Frontend": {
        "tagline": "HTML, CSS, JavaScript, and modern SPA frameworks",
        "concepts": {"a11y": "Semantic HTML, ARIA, keyboard navigation.", "perf": "Core Web Vitals, bundle size, lazy loading."},
    },
    "Data Science": {
        "tagline": "NumPy, Pandas, visualization, and scikit-learn pipelines",
        "concepts": {"bias": "Train/test leakage and fairness in features.", "repro": "Seeds, environment pins, experiment tracking."},
    },
    "DevOps": {
        "tagline": "Culture, CI/CD, IaC, and SRE practices",
        "concepts": {"dora": "Deployment frequency, lead time, MTTR, change failure rate.", "idp": "Internal developer platform golden paths."},
    },
    "ELK": {
        "tagline": "Elasticsearch, Logstash, Kibana, and Elastic Agent",
        "architecture": "Ingest → index → search → visualize. ILM hot/warm/cold tiers.",
        "concepts": {"mapping": "Field types affect aggregation; dynamic mapping risks."},
    },
    "GitHub": {
        "tagline": "Git hosting, Actions CI/CD, and security scanning",
        "concepts": {"actions": "Workflows, jobs, steps, secrets, environments, OIDC to cloud."},
    },
    "GitLab": {
        "tagline": "DevOps platform with integrated CI/CD and registry",
        "concepts": {"pipeline": ".gitlab-ci.yml stages, runners, artifacts."},
    },
    "Bitbucket": {
        "tagline": "Atlassian Git with Pipelines and Jira integration",
        "concepts": {"pipelines": "bitbucket-pipelines.yml, deployment environments."},
    },
    "Helm": {
        "tagline": "Kubernetes package manager for charts and releases",
        "commands": {"install": "helm upgrade --install RELEASE ./chart -f values.yaml --atomic"},
    },
    "Jenkins": {
        "tagline": "Extensible CI server with pipelines and agents",
        "concepts": {"pipeline": "Declarative Jenkinsfile, shared libraries, credentials binding."},
    },
    "ArgoCD": {
        "tagline": "Declarative GitOps continuous delivery for Kubernetes",
        "concepts": {"sync": "Desired state in Git vs live cluster; auto-sync vs manual."},
    },
    "Pulumi": {
        "tagline": "Infrastructure as code in Python, TypeScript, Go",
        "concepts": {"stack": "Stack per environment; config and secrets per stack."},
    },
    "CloudFormation": {
        "tagline": "AWS-native infrastructure templates",
        "concepts": {"stack": "CREATE_COMPLETE, rollback on failure, drift detection."},
    },
    "Packer": {
        "tagline": "Multi-platform image building for immutable infrastructure",
        "concepts": {"builder": "amazon-ebs, googlecompute, docker builders."},
    },
    "OpenShift": {
        "tagline": "Enterprise Kubernetes with Routes and SCCs",
        "concepts": {"scc": "Security Context Constraints replace PSP patterns."},
    },
    "Podman": {
        "tagline": "Daemonless OCI containers and pods on Linux",
        "concepts": {"rootless": "User namespace mapping; podman-compose compatibility."},
    },
    "Nginx": {
        "tagline": "High-performance web server and reverse proxy",
        "concepts": {"worker": "worker_processes auto; upstream keepalive."},
    },
    "VMware": {
        "tagline": "vSphere virtualization — ESXi, vCenter, HA, DRS",
        "concepts": {"vmotion": "Live migration; storage vMotion for disks.", "drs": "Automated load balance across cluster."},
    },
    "Windows": {
        "tagline": "Windows Server, AD, DNS, GPO, and PowerShell",
        "concepts": {"ad": "Domains, OUs, GPO inheritance, FSMO roles."},
    },
    "Security": {
        "tagline": "Cross-cutting security engineering",
        "concepts": {"zero_trust": "Verify explicitly; least privilege; assume breach."},
    },
    "Cisco": {
        "tagline": "Enterprise routing and switching with IOS",
        "concepts": {"vlan": "802.1Q tagging; trunk vs access ports."},
    },
    "pfSense": {
        "tagline": "Open-source firewall and router platform",
        "concepts": {"carp": "High availability failover between firewalls."},
    },
    "MikroTik": {
        "tagline": "RouterOS for ISPs and enterprise edge",
        "concepts": {"bridge": "Hardware offload; VLAN filtering."},
    },
    "Loki": {"tagline": "Grafana Loki log aggregation with LogQL", "concepts": {"labels": "Index by labels not full text — choose labels carefully."}},
    "Tempo": {"tagline": "Grafana Tempo distributed tracing backend", "concepts": {"otel": "OpenTelemetry SDKs emit spans to Tempo."}},
    "Jaeger": {"tagline": "CNCF distributed tracing", "concepts": {"sampling": "Head vs tail sampling trade-offs."}},
    "TypeScript": {"tagline": "Typed JavaScript for large-scale apps", "concepts": {"strict": "strictNullChecks prevents null bugs."}},
    "React": {"tagline": "Component-based UI library", "concepts": {"hooks": "useState, useEffect, useMemo — rules of hooks."}},
    "Next.js": {"tagline": "React framework with SSR and App Router", "concepts": {"rsc": "React Server Components reduce client JS."}},
    "Node.js": {"tagline": "JavaScript runtime for servers", "concepts": {"event_loop": "Non-blocking I/O; avoid CPU on main thread."}},
    "Django": {"tagline": "Python web framework with ORM and admin", "concepts": {"orm": "Migrations track schema; select_related reduces queries."}},
    "FastAPI": {"tagline": "Modern Python ASGI API framework", "concepts": {"pydantic": "Request/response validation and OpenAPI schema."}},
    "MongoDB": {"tagline": "Document database with replica sets and sharding", "concepts": {"shard_key": "Immutable choice — drives data distribution."}},
    "Express.js": {
        "tagline": "Minimal Node.js web framework for REST APIs",
        "concepts": {"middleware": "Request pipeline; error-handling middleware last."},
    },
    "HTML": {"tagline": "Semantic markup for web documents", "concepts": {"semantic": "main, nav, article improve SEO and screen readers."}},
    "CSS": {"tagline": "Stylesheets, layout, and responsive design", "concepts": {"grid": "CSS Grid for 2D layouts; Flexbox for 1D."}},
    "JavaScript": {"tagline": "Language of the web — ES6+ features", "concepts": {"async": "Promises, async/await, fetch API."}},
    "DevSecOps": {
        "tagline": "Security integrated into CI/CD and runtime",
        "concepts": {"sast": "Static analysis in PR.", "dast": "Dynamic scan in staging.", "sbom": "Software bill of materials."},
    },
    "IAM": {
        "tagline": "Identity and access management across cloud and apps",
        "concepts": {"mfa": "Phishing-resistant MFA.", "sso": "SAML/OIDC federation.", "rbac": "Role-based access."},
    },
    "SOC": {
        "tagline": "Security Operations Center monitoring and response",
        "concepts": {"tier1": "Triage alerts.", "tier2": "Investigate.", "tier3": "Hunt and improve detections."},
    },
    "SIEM": {
        "tagline": "Security information and event management",
        "concepts": {"correlation": "Rules map events to MITRE ATT&CK techniques."},
    },
    "Containerd": {
        "tagline": "Industry-standard CRI container runtime",
        "concepts": {"cri": "Kubelet talks CRI; crictl debugs pods.", "namespace": "k8s.io namespace isolates images."},
    },
}


def get_all_profiles() -> dict[str, dict]:
    merged = dict(_BASE)
    for topic, ext in EXTENDED_PROFILES.items():
        base = merged.get(topic, {})
        merged[topic] = {**base, **ext}
    return merged
