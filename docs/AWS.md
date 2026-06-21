# AWS / EKS — enabling the AWS hosting path

> **Status: SCAFFOLD.** Nothing here runs in the default pipeline. The green
> four-droplet launch (`cloud_provider=digitalocean`, `hosting_target=droplets`)
> is completely unaffected. The AWS jobs/scripts are **no-ops until AWS
> credentials exist** — and even then they refuse to provision without an
> explicit `APPLY=1`.

This page describes how to run FixitLab on AWS with **EKS** (true private nodes),
**RDS** (Aurora PostgreSQL), and **ElastiCache** (Redis). The Kubernetes
manifests are shared with DOKS — see [KUBERNETES.md](./KUBERNETES.md).

## What's in the box

```
infra/aws/
  provision-eks.sh      # VPC/subnets/EKS provisioning stub (eksctl OR terraform)
  eksctl-cluster.yaml   # eksctl ClusterConfig (private node groups: app + lab-runners)
infra/terraform/
  main.tf               # full Terraform: VPC, EKS, RDS Aurora, ElastiCache, ECR, S3, CloudFront
infra/k8s/
  base/ + overlays/eks  # the same modular-monolith manifests DOKS uses
```

Two provisioners are supported; pick one with `EKS_PROVISIONER`:

| Provisioner          | Source                          | Notes                              |
| -------------------- | ------------------------------- | ---------------------------------- |
| `eksctl` (default)   | `infra/aws/eksctl-cluster.yaml` | Fast, opinionated, one command.    |
| `terraform`          | `infra/terraform/main.tf`       | Full estate (RDS/ElastiCache/CDN). |

Both create a dedicated VPC across 3 AZs with **private** node subnets and two
managed node groups:

- **app** — `m5.xlarge`, on-demand, 2→50 nodes (API/WS/frontend/celery).
- **lab-runners** — `m5.2xlarge` spot, 2→200 nodes, tainted `workload=lab` so only
  lab workloads schedule there (true private lab isolation).

## Workflow inputs

In **Actions → FixitLab Production → Run workflow**:

| Input             | For EKS    | Gates                                    |
| ----------------- | ---------- | ---------------------------------------- |
| `cloud_provider`  | `aws`      | the `provision-aws` job                  |
| `hosting_target`  | `eks`      | the `deploy-eks` job (also needs `aws`)  |

- `cloud_provider=aws` → **`[AWS] Provision VPC/EKS (scaffold)`** runs.
- `cloud_provider=aws` + `hosting_target=eks` → **`[EKS] Deploy (scaffold)`** also runs.

Both jobs are **standalone** (no `needs` into the droplet chain), gated purely by
`if:`. With the defaults they are skipped and the pipeline is unchanged.

## Required secrets / variables

Set these in **Settings → Secrets and variables → Actions** (Environment
`production`) before enabling:

| Name                       | Type     | Purpose                                  |
| -------------------------- | -------- | ---------------------------------------- |
| `AWS_ACCESS_KEY_ID`        | secret   | AWS auth (or use OIDC role)              |
| `AWS_SECRET_ACCESS_KEY`    | secret   | AWS auth                                 |
| `AWS_REGION`               | variable | default `us-east-1`                      |
| `EKS_PROVISIONER`          | variable | `eksctl` (default) or `terraform`        |

The scripts also accept OIDC/IRSA (`AWS_ROLE_ARN` + `AWS_WEB_IDENTITY_TOKEN_FILE`)
instead of static keys.

## Enabling for real

1. **Provision infra** (gated — needs creds **and** `APPLY=1`):

   ```bash
   # eksctl (default)
   APPLY=1 EKS_PROVISIONER=eksctl AWS_REGION=us-east-1 bash infra/aws/provision-eks.sh
   # or terraform
   APPLY=1 EKS_PROVISIONER=terraform bash infra/aws/provision-eks.sh
   ```

   Without creds → prints the plan and exits 0. With creds but no `APPLY=1` →
   refuses to provision (safety).

   > **Terraform note:** `infra/terraform/main.tf` uses an S3 backend
   > (`fixitlab-terraform-state`) and seeds placeholder DB/ACM values — replace
   > `master_password` with a Secrets Manager reference and set a real ACM cert
   > ARN before applying.

2. **kubeconfig:**

   ```bash
   aws eks update-kubeconfig --name fixitlab-eks --region "$AWS_REGION"
   ```

3. **Install ingress + cert-manager**, then **create the secret** — identical to
   the DOKS steps in [KUBERNETES.md](./KUBERNETES.md). On EKS you may instead use
   the **AWS Load Balancer Controller** (ALB): patch `ingressClassName: alb` and
   the ALB annotations in `infra/k8s/overlays/eks`.

4. **Point datastores at managed services:** set `POSTGRES_HOST` to the RDS
   writer endpoint and `REDIS_HOST` to the ElastiCache primary endpoint (patch
   `infra/k8s/base/configmap.yaml` via the eks overlay).

5. **Deploy the manifests** (images from Docker Hub or re-tagged to ECR):

   ```bash
   cd infra/k8s/overlays/eks
   kustomize edit set image \
     fixitlab/fixitlab-backend=$NS/fixitlab-backend:$TAG \
     fixitlab/fixitlab-frontend=$NS/fixitlab-frontend:$TAG
   kubectl apply -k .
   ```

## Images: Docker Hub vs ECR

This scaffold pulls from **Docker Hub** (the same images the
[Docker Hub pipeline](./DOCKERHUB.md) builds), so EKS works without ECR. To use
ECR instead, `terraform` already creates the repos
(`fixitlab/backend`, `fixitlab/frontend`); re-tag/push there and point the
kustomize images at the ECR URLs.

## Why this is safe for the green pipeline

`provision-aws` and `deploy-eks` are standalone and gated only by `if:` on the
new inputs. Nothing on the four-droplet critical chain depends on them, so a
skipped scaffold job cannot transitively skip
create-cluster/bootstrap/deploy. With the defaults
(`cloud_provider=digitalocean`, `hosting_target=droplets`) both jobs are skipped.
