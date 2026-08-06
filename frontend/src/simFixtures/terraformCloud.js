/** Terraform Cloud / Enterprise UI seed data — merged with backend session state in the simulator. */

export const TFC_ORG = { name: 'fixitlab-training', id: 'org-fixitlab' }

export const TFC_WORKSPACES = [
  { id: 'ws-1', name: 'prod-vpc', project: 'Network', status: 'Applied', runs: 42, lastRun: 'Plan applied', updatedAt: '2026-06-24T09:12:00Z' },
  { id: 'ws-2', name: 'web-tier-asg', project: 'Compute', status: 'Errored', runs: 18, lastRun: 'Apply errored', updatedAt: '2026-06-23T14:05:00Z' },
  { id: 'ws-3', name: 'rds-backup', project: 'Database', status: 'Planned', runs: 7, lastRun: 'Plan finished', updatedAt: '2026-06-22T11:30:00Z' },
  { id: 'ws-4', name: 'iam-baseline', project: 'Security', status: 'No Changes', runs: 31, lastRun: 'Plan: no changes', updatedAt: '2026-06-21T08:00:00Z' },
  { id: 'ws-5', name: 'eks-cluster', project: 'Kubernetes', status: 'Applied', runs: 56, lastRun: 'Applied successfully', updatedAt: '2026-06-20T16:45:00Z' },
  { id: 'ws-6', name: 's3-log-archive', project: 'Storage', status: 'Applied', runs: 12, lastRun: 'Applied successfully', updatedAt: '2026-06-19T10:22:00Z' },
  { id: 'ws-lab', name: 'lab-workspace', project: 'Training', status: 'Planned', runs: 3, lastRun: 'Plan queued', updatedAt: '2026-06-24T08:00:00Z' },
]

export const TFC_RUNS = [
  { id: 'run-101', status: 'Applied', triggeredBy: 't.ponguluri', planCost: '$0.00', time: '4m 12s', createdAt: '2026-06-24T09:08:00Z' },
  { id: 'run-100', status: 'Errored', triggeredBy: 'ci-bot', planCost: '$12.40', time: '2m 01s', createdAt: '2026-06-23T14:02:00Z' },
  { id: 'run-99', status: 'Planned', triggeredBy: 't.ponguluri', planCost: '$8.20', time: '1m 44s', createdAt: '2026-06-22T11:28:00Z' },
  { id: 'run-98', status: 'Applied', triggeredBy: 'webhook', planCost: '$0.00', time: '3m 55s', createdAt: '2026-06-21T07:58:00Z' },
]

export const TFC_VARIABLES = [
  { id: 'v1', key: 'aws_region', value: 'ap-south-1', category: 'terraform', sensitive: false, hcl: false },
  { id: 'v2', key: 'instance_type', value: 't3.medium', category: 'terraform', sensitive: false, hcl: false },
  { id: 'v3', key: 'AWS_ACCESS_KEY_ID', value: '********', category: 'env', sensitive: true, hcl: false },
  { id: 'v4', key: 'tags', value: '{ Environment = "lab" }', category: 'terraform', sensitive: false, hcl: true },
]

export const TFC_MODULES = [
  { id: 'm1', name: 'vpc', provider: 'hashicorp/aws', version: '5.1.2', published: '2026-05-01' },
  { id: 'm2', name: 'eks', provider: 'hashicorp/aws', version: '20.8.0', published: '2026-04-18' },
  { id: 'm3', name: 'rds', provider: 'hashicorp/aws', version: '6.3.0', published: '2026-03-22' },
]

export const TFC_TEAMS = [
  { id: 't1', name: 'platform-admins', access: 'admin', members: 4 },
  { id: 't2', name: 'developers', access: 'write', members: 18 },
  { id: 't3', name: 'auditors', access: 'read', members: 6 },
]

export const TFC_AGENT_POOLS = [
  { id: 'ap1', name: 'default-pool', agents: 3, status: 'healthy' },
  { id: 'ap2', name: 'prod-agents', agents: 5, status: 'healthy' },
]

export const TFC_RUN_LOG = [
  '\x1b[36mTerraform v1.7.5\x1b[0m on linux_amd64',
  '\x1b[32m+ aws_instance.web\x1b[0m will be created',
  '  \x1b[33m~ resource "aws_instance" "web" {\x1b[0m',
  '      \x1b[32m+ ami\x1b[0m = "ami-0c55b159cbfafe1f0"',
  '      \x1b[32m+ instance_type\x1b[0m = "t3.medium"',
  'Plan: 1 to add, 0 to change, 0 to destroy.',
  '\x1b[32mApply complete! Resources: 1 added.\x1b[0m',
]

export const TFC_SIDEBAR = [
  { key: 'org-switcher', label: TFC_ORG.name, icon: null },
  { key: 'projects', label: 'Projects', items: [
    { key: 'workspaces', label: 'Workspaces' },
    { key: 'explorer', label: 'Explorer' },
  ]},
  { key: 'registry', label: 'Registry', items: [
    { key: 'registry-public', label: 'Public Registry' },
    { key: 'registry-private', label: 'Private Registry' },
    { key: 'registry-providers', label: 'Providers' },
    { key: 'registry-modules', label: 'Modules' },
  ]},
  { key: 'settings', label: 'Settings', items: [
    { key: 'settings-general', label: 'General' },
    { key: 'settings-teams', label: 'Teams' },
    { key: 'settings-sso', label: 'SSO' },
    { key: 'settings-cost', label: 'Cost Estimation' },
    { key: 'settings-notifications', label: 'Notifications' },
    { key: 'settings-vcs', label: 'VCS Providers' },
    { key: 'settings-tokens', label: 'API Tokens' },
    { key: 'settings-agents', label: 'Agents' },
    { key: 'settings-audit', label: 'Audit Logs' },
    { key: 'settings-usage', label: 'Usage' },
  ]},
]

export const TFC_STATES = [
  { id: 'st-1', serial: 42, createdAt: '2026-06-24T09:12:00Z', createdBy: 't.ponguluri', resources: 18 },
  { id: 'st-2', serial: 41, createdAt: '2026-06-23T14:05:00Z', createdBy: 'ci-bot', resources: 17 },
]

export const TFC_LOCKS = [
  { id: 'lk-1', operation: 'plan', lockedBy: 'run-101', lockedAt: '2026-06-24T09:08:00Z', age: '4m' },
]

export const TFC_WS_NOTIFICATIONS = [
  { id: 'wn1', name: 'Slack #infra', triggers: 'Errored runs', status: 'enabled' },
  { id: 'wn2', name: 'Email platform', triggers: 'Needs attention', status: 'enabled' },
]

export const TFC_TEAM_ACCESS = [
  { team: 'platform-admins', permission: 'Admin', inherited: false },
  { team: 'developers', permission: 'Write', inherited: true },
  { team: 'auditors', permission: 'Read', inherited: true },
]

export const TFC_HEALTH = [
  { check: 'VCS connection', status: 'passing', detail: 'GitHub connected' },
  { check: 'Remote state', status: 'passing', detail: 'S3 backend reachable' },
  { check: 'Variables', status: 'warning', detail: '1 sensitive var unused' },
  { check: 'Run queue', status: 'passing', detail: '0 queued runs' },
]

export const TFC_SETTINGS_GENERAL = [
  ['Organization name', TFC_ORG.name],
  ['Default execution mode', 'Remote'],
  ['Terraform version', '1.7.5'],
  ['Cost estimation', 'Enabled'],
]

export const TFC_SETTINGS_SSO = [
  ['SAML enabled', 'Yes'],
  ['IdP', 'Okta'],
  ['Enforce SSO', 'Optional'],
]

export const TFC_SETTINGS_VCS = [
  { provider: 'GitHub', org: 'fixitlab', status: 'connected', repos: 12 },
  { provider: 'GitLab', org: '—', status: 'not connected', repos: 0 },
]

export const TFC_SETTINGS_TOKENS = [
  { name: 'ci-bot', created: '2026-01-15', lastUsed: '2026-06-24', scopes: 'plan, apply' },
  { name: 'local-dev', created: '2026-03-01', lastUsed: '2026-06-20', scopes: 'read' },
]

export const TFC_AUDIT_LOG = [
  { time: '2026-06-24T09:08:00Z', user: 't.ponguluri', action: 'run:plan', target: 'lab-workspace' },
  { time: '2026-06-23T14:02:00Z', user: 'ci-bot', action: 'run:apply', target: 'web-tier-asg' },
  { time: '2026-06-22T11:28:00Z', user: 't.ponguluri', action: 'variable:create', target: 'aws_region' },
]

export const TFC_USAGE = [
  { metric: 'Managed resources', value: '1,248', limit: '5,000' },
  { metric: 'Runs this month', value: '342', limit: 'Unlimited' },
  { metric: 'Policy checks', value: '89', limit: 'Unlimited' },
]
