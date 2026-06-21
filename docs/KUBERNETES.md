# Kubernetes (DOKS) — enabling the managed-Kubernetes path

> **Status: SCAFFOLD.** Nothing here runs in the default pipeline. The green
> four-droplet launch (`cloud_provider=digitalocean`, `hosting_target=droplets`)
> is completely unaffected. The DOKS jobs/manifests are no-ops until you opt in
> **and** provide cluster credentials.

FixitLab ships portable, modular-monolith Kubernetes manifests under
[`infra/k8s/`](../infra/k8s) that work on **both** DigitalOcean Kubernetes (DOKS)
and AWS EKS. This page covers DOKS; for EKS see [AWS.md](./AWS.md).

## What's in the box

```
infra/k8s/
  base/                 # shared manifests (DOKS + EKS)
    namespace.yaml
    configmap.yaml      # non-secret runtime config (datastore hosts, etc.)
    secret.example.yaml # KEY template only — never real values
    backend.yaml        # Django ASGI Deployment + Service + HPA
    celery.yaml         # celery worker (HPA) + beat (singleton)
    frontend.yaml       # nginx-served React Deployment + Service + HPA
    ingress.yaml        # WebSocket-ready nginx Ingress + cert-manager TLS
    kustomization.yaml
  overlays/
    doks/kustomization.yaml
    eks/kustomization.yaml
  provision-doks.sh     # doctl cluster create stub (no-op until APPLY=1)
```

It is a **modular monolith**: one backend image (`fixitlab-backend`) serves API,
WebSocket, and admin; one frontend image (`fixitlab-frontend`) serves the SPA.
Both images come from **Docker Hub** — the same images the
[Docker Hub pipeline](./DOCKERHUB.md) builds (`<namespace>/fixitlab-backend`,
`<namespace>/fixitlab-frontend`).

## Workflow inputs

In **Actions → FixitLab Production → Run workflow**:

| Input             | For DOKS        | Notes                                         |
| ----------------- | --------------- | --------------------------------------------- |
| `cloud_provider`  | `digitalocean`  | default                                       |
| `hosting_target`  | `doks`          | gates the `deploy-doks` job                   |

With `hosting_target=doks`, the standalone **`[DOKS] Deploy (scaffold)`** job runs.
It is gated purely by `if:` and has no `needs` into the droplet chain, so it can
never affect the four-droplet pipeline. By default it **prints what it would do**
and exits cleanly.

## Enabling for real

1. **Provision the cluster.** A DO token is usually already present
   (`DO_API_TOKEN` or inside `PRODUCTION_ENV_B64`). Creating a *paid* managed
   cluster requires an explicit gate:

   ```bash
   APPLY=1 DO_REGION=blr1 bash infra/k8s/provision-doks.sh
   ```

   This creates an autoscaling DOKS cluster (`fixitlab-doks`) and saves the
   kubeconfig. Without `APPLY=1` it is a no-op.

2. **Install ingress + TLS** (once per cluster):

   ```bash
   helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
   helm install ingress-nginx ingress-nginx/ingress-nginx
   helm repo add jetstack https://charts.jetstack.io
   helm install cert-manager jetstack/cert-manager \
     --set crds.enabled=true
   # then create a letsencrypt-prod ClusterIssuer (see cert-manager docs)
   ```

3. **Create the secret** from the rotated env (never commit it):

   ```bash
   kubectl create namespace fixitlab
   kubectl -n fixitlab create secret generic fixitlab-secrets \
     --from-env-file=.env.production
   ```

   `.env.production` is produced/rotated by
   [`scripts/ci-generate-secrets.py`](../scripts/ci-generate-secrets.py).
   For production, prefer **Sealed Secrets** or the **External Secrets Operator**
   backed by Vault (the platform already runs Vault — see
   [VAULT_SETUP.md](./VAULT_SETUP.md)).

4. **Point datastores at managed services** (recommended): edit
   `infra/k8s/base/configmap.yaml` (or patch in the overlay) so `POSTGRES_HOST` /
   `REDIS_HOST` reference DO Managed PostgreSQL / Managed Redis private
   hostnames, mirroring how the four-droplet topology points D2 at D3.

5. **Deploy the manifests**, pinning the Docker Hub image tag:

   ```bash
   cd infra/k8s/overlays/doks
   kustomize edit set image \
     fixitlab/fixitlab-backend=$NS/fixitlab-backend:$TAG \
     fixitlab/fixitlab-frontend=$NS/fixitlab-frontend:$TAG
   kubectl apply -k .
   ```

   (`$NS` = your Docker Hub namespace, `$TAG` = the commit SHA the pipeline pushed.)

## Scaling

- **backend**: HPA 2→50 on CPU 65% / mem 75%.
- **celery-worker**: HPA 2→30 on CPU 70%. **celery-beat**: singleton (Recreate).
- **frontend**: HPA 2→10 on CPU 70%.
- Add the **cluster-autoscaler** (DOKS node pools already autoscale 3→20 in the
  provision stub) so node capacity follows pod demand.

## Why this is safe for the green pipeline

The `deploy-doks` job is **standalone**: nothing in the four-droplet chain
`needs` it, and it `needs` nothing on that chain. A skipped job only cascades a
skip to dependents that lack `always()`; since no critical job depends on
`deploy-doks`, selecting droplets (the default) leaves the pipeline byte-for-byte
unchanged.
