# FixitLab task runner (audit Z6-13).
#
# There was no Makefile/justfile/Taskfile, so setup was tribal knowledge spread
# across four docs. The seed commands in particular are good but there are seven of
# them and **the order matters** — you had to know both the names and the sequence.
#
# The seed order below is not invented: it is transcribed from
# `scripts/platform-start.sh` and `.github/workflows/production.yml`, which are the
# two places that actually run it. If those change, change this — a task runner that
# drifts from the deploy path is worse than none, because it looks authoritative.
#
# Everything here uses the project virtualenv explicitly. The system `python3` on
# macOS is 3.9 and too old for this codebase (`str | None` syntax), which fails with
# a confusing TypeError deep inside an unrelated import.

PY := backend/.venv/bin/python
MANAGE := cd backend && ../$(PY) manage.py
TEST_SETTINGS := DJANGO_SETTINGS_MODULE=config.test_settings

.DEFAULT_GOAL := help
.PHONY: help setup test test-fast lint lint-fix check migrate migrations seed \
        seed-scenarios build front-build front-lint gates scan-secrets \
        scan-graders lint-scenarios clean

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

# ── Setup ────────────────────────────────────────────────────────────────────

setup:  ## Create the venv and install backend + frontend deps
	python3 -m venv backend/.venv || true
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -r backend/requirements.txt
	cd frontend && npm ci

# ── Tests and gates ──────────────────────────────────────────────────────────

test:  ## Full backend suite (~20 min). Runs BOTH tests/ and apps/ — CI does too.
	cd backend && $(TEST_SETTINGS) ../$(PY) manage.py test tests apps

test-fast:  ## One module, e.g. make test-fast M=tests.test_mfa
	@test -n "$(M)" || (echo "usage: make test-fast M=tests.test_mfa" && exit 1)
	cd backend && $(TEST_SETTINGS) ../$(PY) manage.py test $(M)

lint:  ## ruff over backend + scripts (the CI gate)
	$(PY) -m ruff check --config backend/ruff.toml backend/ scripts/

lint-fix:  ## ruff with --fix
	$(PY) -m ruff check --config backend/ruff.toml --fix backend/ scripts/

front-lint:  ## eslint over the frontend
	cd frontend && npm run lint

front-build:  ## Production frontend build
	cd frontend && npm run build

scan-secrets:  ## Leaked-credential scan over tracked files
	bash scripts/check-no-secrets-in-git.sh

scan-graders:  ## Fail-open grader gate (minutes, not seconds — ~7.3k scenarios)
	cd backend && ../$(PY) ../scripts/scan_grader_integrity.py --check

lint-scenarios:  ## Scenario YAML validation
	$(PY) scripts/lint_scenarios.py --all --max-failures 0

# Deliberately ordered fast-to-slow, so the cheap gates fail before you spend
# 20 minutes on the suite. This mirrors what CI enforces.
gates: lint check front-lint front-build scan-secrets test  ## Everything CI checks, cheapest first

# ── Database ─────────────────────────────────────────────────────────────────

check:  ## Fail if a model change has no migration (CI gate)
	cd backend && $(TEST_SETTINGS) ../$(PY) manage.py makemigrations --check --dry-run

migrations:  ## Generate migrations for changed models
	cd backend && $(TEST_SETTINGS) ../$(PY) manage.py makemigrations

migrate:  ## Apply migrations
	cd backend && ../$(PY) manage.py migrate

# ── Seeding ──────────────────────────────────────────────────────────────────
#
# Order transcribed from scripts/platform-start.sh. scenarios first because
# projects, certifications and journeys all reference them.

seed:  ## Seed everything, in the order the deploy actually uses
	$(MANAGE) seed_scenarios --dir ../scenarios
	$(MANAGE) seed_admin_demo
	$(MANAGE) seed_projects
	$(MANAGE) seed_certifications
	$(MANAGE) seed_learning_journeys
	$(MANAGE) seed_tutorials
	$(MANAGE) seed_interview_data

seed-scenarios:  ## Re-seed scenarios only (merge, does not delete)
	$(MANAGE) seed_scenarios --dir ../scenarios --merge-only

clean:  ## Remove build artefacts and caches
	find backend -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null || true
	rm -rf frontend/dist
