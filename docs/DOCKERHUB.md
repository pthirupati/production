# Docker Hub Image Pipeline (P5)

Build each FixitLab image **once** in CI, tag it by commit SHA, push it to Docker
Hub, and have the deploy nodes **pull** the pinned image instead of rebuilding it on
every droplet. This gives versioned, rollback-able images and is the foundation for
the k8s phases (P6/P7).

> **This feature is fully OFF by default.** With no Docker Hub configuration, the
> production pipeline behaves exactly as before: every node runs
> `docker compose up --build` and builds images locally from source. Nothing in the
> default deploy changes until you set the `USE_DOCKERHUB` variable below.

---

## What it does when enabled

A gated workflow job, **`build-push-images`**, runs early in `FixitLab Production`
and builds the three images from the **same Dockerfiles the compose files use**:

| Image                          | Build context | Dockerfile              | Compose service(s)                          |
|--------------------------------|---------------|-------------------------|---------------------------------------------|
| `<ns>/fixitlab-backend`        | `./backend`   | `Dockerfile`            | `backend`, `celery_*` (share one image)     |
| `<ns>/fixitlab-frontend`       | `./frontend`  | `Dockerfile.prod`       | `frontend-prod`                             |
| `<ns>/fixitlab-gateway`        | `./gateway`   | `Dockerfile.prod`       | `gateway`                                   |

Each is pushed with **two tags**:

- `<ns>/fixitlab-<svc>:<git-sha>` — the immutable, per-commit tag (12-char SHA)
- `<ns>/fixitlab-<svc>:latest` — moving pointer to the most recent successful build

`<ns>` is the **namespace** (`DOCKERHUB_NAMESPACE` var, defaulting to your
`DOCKERHUB_USERNAME`). Postgres, Redis, RabbitMQ, pgBouncer, Vault and certbot are
untouched — they already use upstream public images.

The deploy then sets `IMAGE_TAG=<git-sha>` and pulls those images on the nodes
instead of building (see "How compose pulls vs builds").

---

## What to set

All configuration lives in the repo's **`production` environment** (Settings →
Environments → production), matching the existing `DO_REGION` / `DO_SIZE` pattern.

### 1. The gate — a repository/environment *Variable*

| Name           | Type     | Value    | Effect                                                        |
|----------------|----------|----------|---------------------------------------------------------------|
| `USE_DOCKERHUB`| Variable | `true`   | Turns the image pipeline ON. Any other value / unset = OFF.   |

We gate on a **variable** (not secret presence) because it is explicit, visible in
the Settings UI, and consistent with `vars.DO_REGION` / `vars.DO_SIZE`. The job line
is literally:

```yaml
build-push-images:
  if: vars.USE_DOCKERHUB == 'true'
```

### 2. Credentials — *Secrets*

| Name                  | Type   | Required | Notes                                                  |
|-----------------------|--------|----------|--------------------------------------------------------|
| `DOCKERHUB_USERNAME`  | Secret | yes      | Docker Hub account used to log in and (by default) the image namespace. |
| `DOCKERHUB_TOKEN`     | Secret | yes      | Docker Hub **access token** (Account → Security → New Access Token, Read & Write). Do **not** use your password. |

### 3. Namespace override — optional *Variable*

| Name                  | Type     | Default                | Notes                                              |
|-----------------------|----------|------------------------|----------------------------------------------------|
| `DOCKERHUB_NAMESPACE` | Variable | `DOCKERHUB_USERNAME`   | Set this to push under an org, e.g. `fixitlab`.    |

**Safety valve:** if `USE_DOCKERHUB == 'true'` but `DOCKERHUB_USERNAME` /
`DOCKERHUB_TOKEN` are missing, the job logs a notice and **exits cleanly (0)** —
it never fails the pipeline, and the nodes fall back to on-node builds.

---

## How `IMAGE_TAG` flows

```
build-push-images (tag = ${GITHUB_SHA::12}, pushes :sha + :latest)
   │  outputs: image_tag, namespace, pushed
   ├──────────────► single-host deploy
   │                  passes IMAGE_TAG / FIXITLAB_IMAGE_NS / PULL_IMAGES=1
   │                  over SSH → ci-remote-platform.sh → platform-start.sh
   │
   └──────────────► four-droplet create-cluster
                      writes USE_DOCKERHUB/IMAGE_TAG/FIXITLAB_IMAGE_NS into the
                      cluster artifact (_cluster/cluster_ips.env)
                         │  every job's "Load edge host" step sources it into $GITHUB_ENV
                         └► deploy-cluster → ci-cluster-deploy.sh
                              prepends IMAGE_TAG/PULL_IMAGES to the D1 (edge) and
                              D2 (app) remote deploy commands
```

The tag is the 12-char commit SHA, so every commit deployed via this pipeline has a
corresponding immutable image set on Docker Hub.

---

## How compose pulls vs builds

Each of `backend` / `frontend-prod` / `gateway` (and the celery services that share
the backend image) now declares **both** a `build:` block and an `image:` name in
`docker-compose.{app,edge,prod}.yml`:

```yaml
backend:
  build: ./backend
  image: ${FIXITLAB_IMAGE_NS:-fixitlab}/fixitlab-backend:${IMAGE_TAG:-latest}
```

- **Default (build on node):** `IMAGE_TAG` unset → resolves to
  `fixitlab/fixitlab-backend:latest`, used purely as the *local tag* of the image
  Compose builds from `./backend`. `platform-start.sh` runs `up -d --build` exactly
  as before.
- **Pull pinned image:** when the deploy sets `PULL_IMAGES=1` + `IMAGE_TAG=<sha>`
  (+ optional `FIXITLAB_IMAGE_NS`), `platform-start.sh` instead runs
  `docker compose pull` then `up -d --no-build`, so the node fetches the exact
  CI-built `…:<sha>` image. This only happens when `USE_DOCKERHUB` is on.

`docker-compose.data.yml` (Postgres + pgBouncer) is intentionally **not** modified —
the database image is not part of the pushed set.

---

## Rollback by tag

Because every commit's images are retained on Docker Hub, rolling back is just
re-deploying with an older tag — no rebuild required.

**Option A — redeploy an old commit (recommended).** Run *FixitLab Production* with
`git_ref` set to the older commit/tag. CI rebuilds+pushes that commit's images (or
reuses them if already pushed) and the nodes pull the matching `:<sha>`.

**Option B — pin an existing pushed tag without a code change.** On the relevant
node(s), set the tag in the environment and re-run the start script so Compose pulls
that exact image:

```bash
# Single host:
cd /opt/fixitlab
PULL_IMAGES=1 IMAGE_TAG=<old-sha> FIXITLAB_IMAGE_NS=<ns> \
  ./scripts/ci-remote-platform.sh deploy

# Four-droplet (run on D1 edge and D2 app):
PULL_IMAGES=1 IMAGE_TAG=<old-sha> FIXITLAB_IMAGE_NS=<ns> CLUSTER_ROLE=app \
  BUILD_SCENARIOS=false ./scripts/ci-remote-platform.sh deploy
```

Inspect what is available before rolling back:

```bash
# Tags pushed for a repo (needs jq):
curl -s "https://hub.docker.com/v2/repositories/<ns>/fixitlab-backend/tags?page_size=100" \
  | jq -r '.results[].name'
```

To roll **forward** again, deploy `latest` or the newest commit's SHA.

---

## Quick enable checklist

1. Create a Docker Hub access token (Read & Write).
2. In the `production` environment, add **secrets** `DOCKERHUB_USERNAME`,
   `DOCKERHUB_TOKEN`.
3. (Optional) add **variable** `DOCKERHUB_NAMESPACE` if pushing under an org.
4. Add **variable** `USE_DOCKERHUB=true`.
5. Run *FixitLab Production* (`deploy`). `build-push-images` builds+pushes; the
   deploy pulls the pinned `:<sha>` images.
6. To disable, delete/unset `USE_DOCKERHUB` — the next deploy builds on-node again.
