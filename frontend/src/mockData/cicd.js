/**
 * cicd.js — CI/CD pipeline seed data for the DevOps pipeline simulator.
 *
 * Raw YAML/Groovy config text per provider (parseable by pipelineParser.js) plus
 * a faults catalog keyed by scenario slug so labs can script failures/recovery
 * that map onto isDevOpsPipelineLab (slug regex:
 *   jenkins|gitlab|pipeline|argocd|flux|helm|sonar|ci-pipeline|cicd).
 *
 * Export style mirrors mockData/awx.js: named UPPER_SNAKE consts.
 */

import { PROVIDERS } from '../components/devops/pipelineModel'

// ─────────────────────────────────────────────────────────────────────────────
// GitLab CI seeds
// ─────────────────────────────────────────────────────────────────────────────

export const GITLAB_WEBAPP_CI = `stages:
  - build
  - test
  - deploy

build:
  stage: build
  image: node:18-alpine
  script:
    - npm ci
    - npm run build
  artifacts:
    paths:
      - dist/

test:
  stage: test
  image: node:18-alpine
  script:
    - npm test

deploy:
  stage: deploy
  image: alpine/k8s:1.28.0
  environment: production
  when: manual
  script:
    - kubectl apply -f k8s/
`

export const GITLAB_MICROSERVICE_CI = `stages:
  - build
  - test
  - scan
  - deploy

build:
  stage: build
  image: golang:1.22
  script:
    - go build ./...

unit-test:
  stage: test
  script:
    - go test ./...

integration-test:
  stage: test
  script:
    - make integration

sonar:
  stage: scan
  needs:
    - unit-test
  script:
    - sonar-scanner

deploy-staging:
  stage: deploy
  environment: staging
  script:
    - helm upgrade webapp ./chart

deploy-prod:
  stage: deploy
  environment: production
  when: manual
  needs:
    - deploy-staging
  script:
    - helm upgrade webapp ./chart --set env=prod
`

export const GITLAB_BROKEN_CI = `stages:
  - build
  - test
  - deploy

build:
  stage: build
  image: node:18-alpinee
  script:
    - npm ci
    - npm run build

test:
  stage: test
  script:
    - npm test

deploy:
  stage: deploy
  environment: production
  script:
    - kubectl apply -f k8s/
`

// ─────────────────────────────────────────────────────────────────────────────
// GitHub Actions seeds
// ─────────────────────────────────────────────────────────────────────────────

export const GITHUB_CI_YAML = `name: CI

on:
  push:
    branches: [ main ]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4
      - name: Install
        run: npm ci
      - name: Build
        run: npm run build

  test:
    runs-on: ubuntu-latest
    needs: build
    steps:
      - name: Test
        run: npm test

  deploy:
    runs-on: ubuntu-latest
    needs: test
    environment: production
    steps:
      - name: Deploy
        run: kubectl apply -f k8s/
`

export const GITHUB_MATRIX_YAML = `name: Build and Deploy

on: [push]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - name: Lint
        run: npm run lint

  build:
    runs-on: ubuntu-latest
    steps:
      - name: Build
        run: npm run build

  test:
    runs-on: ubuntu-latest
    needs: build
    steps:
      - name: Test
        run: npm test

  deploy:
    runs-on: ubuntu-latest
    needs: [test, lint]
    environment: production
    steps:
      - name: Sync
        run: argocd app sync webapp
`

export const GITHUB_BROKEN_YAML = `name: CI

on: [push]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - name: Build
        run: docker build -t app:latest .

  deploy:
    runs-on: ubuntu-latest
    needs: build
    environment: production
    steps:
      - name: Deploy
        run: kubectl apply -f k8s/
`

// ─────────────────────────────────────────────────────────────────────────────
// Jenkins seeds (declarative pipeline)
// ─────────────────────────────────────────────────────────────────────────────

export const JENKINS_DECLARATIVE = `pipeline {
  agent any
  stages {
    stage('Build') {
      steps {
        sh 'mvn clean package -DskipTests'
      }
    }
    stage('Test') {
      steps {
        sh 'mvn test'
      }
    }
    stage('SonarQube') {
      steps {
        sh 'sonar-scanner'
      }
    }
    stage('Deploy') {
      steps {
        input message: 'Deploy to production?'
        sh 'kubectl apply -f k8s/'
      }
    }
  }
}
`

export const JENKINS_DOCKER_PIPELINE = `pipeline {
  agent any
  stages {
    stage('Checkout') {
      steps {
        sh 'git checkout main'
      }
    }
    stage('Build Image') {
      steps {
        sh 'docker build -t fixitlab/webapp:1.2.3 .'
      }
    }
    stage('Push') {
      steps {
        sh 'docker push fixitlab/webapp:1.2.3'
      }
    }
    stage('Deploy') {
      steps {
        sh 'helm upgrade webapp ./chart'
      }
    }
  }
}
`

export const JENKINS_BROKEN_PIPELINE = `pipeline {
  agent any
  stages {
    stage('Build') {
      steps {
        sh 'mvn clean package'
      }
    }
    stage('Test') {
      steps {
        sh 'mvn test'
      }
    }
    stage('Deploy') {
      steps {
        sh 'kubectl apply -f k8s/'
      }
    }
  }
}
`

// ─────────────────────────────────────────────────────────────────────────────
// Seed pipeline catalog (grouped by provider) — raw config for the parser.
// ─────────────────────────────────────────────────────────────────────────────

export const CICD_SEED_PIPELINES = {
  [PROVIDERS.GITLAB]: [
    { slug: 'gitlab-webapp', provider: PROVIDERS.GITLAB, title: 'Web app (build → test → manual deploy)', file: '.gitlab-ci.yml', source: GITLAB_WEBAPP_CI },
    { slug: 'gitlab-microservice', provider: PROVIDERS.GITLAB, title: 'Microservice (fan-out tests, staging → prod gate)', file: '.gitlab-ci.yml', source: GITLAB_MICROSERVICE_CI },
    { slug: 'gitlab-broken', provider: PROVIDERS.GITLAB, title: 'Broken pipeline (bad image tag)', file: '.gitlab-ci.yml', source: GITLAB_BROKEN_CI },
  ],
  [PROVIDERS.GITHUB]: [
    { slug: 'github-ci', provider: PROVIDERS.GITHUB, title: 'CI (build → test → deploy)', file: '.github/workflows/ci.yml', source: GITHUB_CI_YAML },
    { slug: 'github-matrix', provider: PROVIDERS.GITHUB, title: 'Build + Deploy (parallel lint, ArgoCD sync)', file: '.github/workflows/deploy.yml', source: GITHUB_MATRIX_YAML },
    { slug: 'github-broken', provider: PROVIDERS.GITHUB, title: 'Broken deploy (missing kubeconfig)', file: '.github/workflows/ci.yml', source: GITHUB_BROKEN_YAML },
  ],
  [PROVIDERS.JENKINS]: [
    { slug: 'jenkins-declarative', provider: PROVIDERS.JENKINS, title: 'Declarative (build → test → sonar → approval)', file: 'Jenkinsfile', source: JENKINS_DECLARATIVE },
    { slug: 'jenkins-docker', provider: PROVIDERS.JENKINS, title: 'Docker build & push → helm deploy', file: 'Jenkinsfile', source: JENKINS_DOCKER_PIPELINE },
    { slug: 'jenkins-broken', provider: PROVIDERS.JENKINS, title: 'Broken pipeline (OOM in tests)', file: 'Jenkinsfile', source: JENKINS_BROKEN_PIPELINE },
  ],
}

/** Flat list of all seed pipelines (handy for pickers/tests). */
export const CICD_SEED_PIPELINE_LIST = [
  ...CICD_SEED_PIPELINES[PROVIDERS.GITLAB],
  ...CICD_SEED_PIPELINES[PROVIDERS.GITHUB],
  ...CICD_SEED_PIPELINES[PROVIDERS.JENKINS],
]

// ─────────────────────────────────────────────────────────────────────────────
// Faults catalog — keyed by scenario slug. Each entry maps to the engine's
// `faults` map: { [jobId]: { failAtStep?, message?, exitCode?, flaky?, always?, approvalTimeout? } }.
//
// jobId keys are the slugified job/stage ids the parsers produce (e.g. 'build',
// 'deploy', 'deploy-prod', 'unit-test'). Applying a catalog entry with a jobId
// that isn't in the current pipeline is a harmless no-op.
// ─────────────────────────────────────────────────────────────────────────────

export const CICD_FAULTS_CATALOG = {
  'bad-image-tag': {
    label: 'Bad Docker image tag',
    hint: 'The build stage references an image tag that does not exist in the registry.',
    faults: {
      build: { failAtStep: 0, exitCode: 1, message: 'manifest for node:18-alpinee not found: manifest unknown' },
    },
  },
  'oom-test': {
    label: 'Out-of-memory in tests',
    hint: 'The test job is killed by the OOM killer — reduce parallelism or bump the runner memory.',
    faults: {
      test: { failAtStep: 'test', exitCode: 137, message: 'Container killed (OOMKilled): exit code 137' },
      'unit-test': { failAtStep: 'test', exitCode: 137, message: 'Container killed (OOMKilled): exit code 137' },
    },
  },
  'flaky-test': {
    label: 'Flaky test',
    hint: 'The test job fails intermittently (~40%). Retry or quarantine the flaky spec.',
    faults: {
      test: { flaky: 0.4, message: 'AssertionError: expected 200 to equal 503 (flaky network mock)' },
      'unit-test': { flaky: 0.4, message: 'AssertionError: expected 200 to equal 503 (flaky network mock)' },
      'integration-test': { flaky: 0.4, message: 'timeout waiting for service (flaky)' },
    },
  },
  'missing-secret': {
    label: 'Missing CI secret',
    hint: 'A required secret/variable is not set, so the job cannot authenticate.',
    faults: {
      build: { failAtStep: 0, exitCode: 1, message: 'Error: required variable REGISTRY_TOKEN is empty or unset' },
      deploy: { failAtStep: 0, exitCode: 1, message: 'Error: required variable KUBE_TOKEN is empty or unset' },
    },
  },
  'kubeconfig-unauthorized': {
    label: 'kubeconfig unauthorized on deploy',
    hint: 'The deploy stage kubeconfig lacks RBAC — the API server returns 401/403.',
    faults: {
      deploy: { failAtStep: 'kubectl', exitCode: 1, message: 'error: You must be logged in to the server (Unauthorized)' },
      'deploy-prod': { failAtStep: 0, exitCode: 1, message: 'error: forbidden: User "ci-bot" cannot patch deployments (RBAC)' },
      'deploy-staging': { failAtStep: 0, exitCode: 1, message: 'error: You must be logged in to the server (Unauthorized)' },
    },
  },
  'approval-timeout': {
    label: 'Approval timeout',
    hint: 'The manual deploy gate is never approved and eventually times out.',
    faults: {
      deploy: { approvalTimeout: true },
      'deploy-prod': { approvalTimeout: true },
    },
  },
}

/** Ordered list of fault scenario slugs (for pickers/tests). */
export const CICD_FAULT_SLUGS = Object.keys(CICD_FAULTS_CATALOG)

/**
 * Map an arbitrary lab scenario slug onto a fault catalog entry using keyword
 * heuristics. Returns the catalog entry (with `.faults`) or null.
 */
export function faultsForScenario(slug) {
  const s = String(slug || '').toLowerCase()
  if (!s) return null
  if (/image|tag|manifest/.test(s)) return CICD_FAULTS_CATALOG['bad-image-tag']
  if (/oom|memory|killed/.test(s)) return CICD_FAULTS_CATALOG['oom-test']
  if (/flaky|intermittent|retry/.test(s)) return CICD_FAULTS_CATALOG['flaky-test']
  if (/secret|token|credential|vault/.test(s)) return CICD_FAULTS_CATALOG['missing-secret']
  if (/kubeconfig|rbac|unauthorized|forbidden|argocd|flux|helm|kubectl/.test(s)) return CICD_FAULTS_CATALOG['kubeconfig-unauthorized']
  if (/approval|gate|manual|timeout/.test(s)) return CICD_FAULTS_CATALOG['approval-timeout']
  return null
}

/**
 * Pick a seed pipeline for a lab scenario slug. Falls back to the GitLab web app
 * pipeline. Providers are matched by the isDevOpsPipelineLab keyword tokens.
 */
export function pipelineForScenario(slug) {
  const s = String(slug || '').toLowerCase()
  if (/jenkins/.test(s)) return CICD_SEED_PIPELINES[PROVIDERS.JENKINS][0]
  if (/github|gh-actions|actions/.test(s)) return CICD_SEED_PIPELINES[PROVIDERS.GITHUB][0]
  if (/gitlab/.test(s)) return CICD_SEED_PIPELINES[PROVIDERS.GITLAB][0]
  return CICD_SEED_PIPELINES[PROVIDERS.GITLAB][0]
}
