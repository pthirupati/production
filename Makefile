# FixitLab Makefile — Build, run, test, deploy commands

.PHONY: help dev up down build push migrate seed test lint clean scenarios deploy

DOCKER_COMPOSE = docker compose
ECR_REGISTRY   ?= fixitlab

help: ## Show available commands
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ─── Development ─────────────────────────────────────────

dev: ## Start all services in development mode
	$(DOCKER_COMPOSE) up --build

up: ## Start all services (detached)
	$(DOCKER_COMPOSE) up -d --build

down: ## Stop all services
	$(DOCKER_COMPOSE) down

logs: ## Tail logs for all services
	$(DOCKER_COMPOSE) logs -f

restart: ## Restart all services
	$(DOCKER_COMPOSE) restart

shell: ## Open Django shell
	$(DOCKER_COMPOSE) exec backend python manage.py shell

dbshell: ## Open PostgreSQL shell
	$(DOCKER_COMPOSE) exec database psql -U fixitlab -d fixitlab

# ─── Database ────────────────────────────────────────────

migrate: ## Run Django migrations
	$(DOCKER_COMPOSE) exec backend python manage.py migrate

makemigrations: ## Create new migrations
	$(DOCKER_COMPOSE) exec backend python manage.py makemigrations

seed: ## Seed database with initial data (technologies + scenarios)
	$(DOCKER_COMPOSE) exec backend python manage.py loaddata initial_data || true
	$(DOCKER_COMPOSE) exec backend python manage.py seed_scenarios || true

superuser: ## Create superuser
	$(DOCKER_COMPOSE) exec backend python manage.py createsuperuser

# ─── Scenarios ───────────────────────────────────────────

scenarios: ## Build all scenario Docker images
	@echo "Building scenario images..."
	@for dir in scenarios/*/*; do \
		if [ -f "$$dir/Dockerfile" ]; then \
			SLUG=$$(basename $$dir); \
			echo "  Building scenario: $$SLUG"; \
			docker build -t $(ECR_REGISTRY)/scenario-$$SLUG:latest $$dir; \
		fi; \
	done
	@echo "Done. Built scenario images."

# ─── Testing ─────────────────────────────────────────────

test: ## Run backend tests
	$(DOCKER_COMPOSE) exec backend python manage.py test --verbosity=2

test-e2e: ## Run end-to-end smoke tests
	docker build -t fixitlab-e2e ./test
	docker run --network fixitlab_net fixitlab-e2e

lint: ## Lint backend code
	$(DOCKER_COMPOSE) exec backend flake8 --max-line-length=120 --exclude=migrations .

# ─── Build & Push ────────────────────────────────────────

build: ## Build all Docker images for production
	docker build -t $(ECR_REGISTRY)/backend:latest ./backend
	docker build -f frontend/Dockerfile.prod -t $(ECR_REGISTRY)/frontend:latest ./frontend
	$(MAKE) scenarios

push: ## Push images to container registry
	docker push $(ECR_REGISTRY)/backend:latest
	docker push $(ECR_REGISTRY)/frontend:latest
	@for dir in scenarios/*/*; do \
		if [ -f "$$dir/Dockerfile" ]; then \
			SLUG=$$(basename $$dir); \
			docker push $(ECR_REGISTRY)/scenario-$$SLUG:latest; \
		fi; \
	done

# ─── Deploy ──────────────────────────────────────────────

deploy: ## Deploy to Kubernetes
	kubectl apply -f infra/kubernetes/deployment.yaml
	kubectl -n fixitlab rollout status deployment/backend --timeout=300s
	kubectl -n fixitlab rollout status deployment/frontend --timeout=300s

deploy-migrate: ## Run migrations on deployed cluster
	kubectl -n fixitlab exec deployment/backend -- python manage.py migrate --noinput

# ─── Cleanup ─────────────────────────────────────────────

clean: ## Remove all containers, volumes, and images
	$(DOCKER_COMPOSE) down -v --rmi local
	docker system prune -f

clean-labs: ## Kill all running lab containers
	docker ps -q --filter "name=fixitlab-lab-" | xargs -r docker rm -f
