/** AWX / Ansible Tower UI seed data */

export const AWX_SIDEBAR = [
  { key: 'dashboard', label: 'Dashboard' },
  { key: 'jobs', label: 'Jobs' },
  { key: 'schedules', label: 'Schedules' },
  { key: 'activity', label: 'Activity Stream' },
  { key: 'approvals', label: 'Workflow Approvals' },
  { key: 'templates', label: 'Templates', items: [
    { key: 'job-templates', label: 'Job Templates' },
    { key: 'workflow-templates', label: 'Workflow Templates' },
  ]},
  { key: 'credentials', label: 'Credentials' },
  { key: 'projects', label: 'Projects' },
  { key: 'inventories', label: 'Inventories' },
  { key: 'hosts', label: 'Hosts' },
  { key: 'organizations', label: 'Organizations' },
  { key: 'users', label: 'Users' },
  { key: 'teams', label: 'Teams' },
  { key: 'instance-groups', label: 'Instance Groups' },
  { key: 'execution-envs', label: 'Execution Environments' },
  { key: 'applications', label: 'Applications' },
  { key: 'notifications', label: 'Notifications' },
  { key: 'mgmt-jobs', label: 'Management Jobs' },
  { key: 'settings', label: 'Settings', items: [
    { key: 'settings-auth', label: 'Authentication' },
    { key: 'settings-jobs', label: 'Jobs' },
    { key: 'settings-system', label: 'System' },
    { key: 'settings-ui', label: 'User Interface' },
    { key: 'settings-subscription', label: 'Subscription' },
  ]},
]

export const AWX_DASHBOARD_STATS = [
  { label: 'Hosts', value: 24, color: '#EE0000' },
  { label: 'Failed Hosts', value: 2, color: '#c0392b' },
  { label: 'Inventories', value: 4, color: '#2980b9' },
  { label: 'Projects', value: 6, color: '#27ae60' },
  { label: 'Job Templates', value: 11, color: '#8e44ad' },
  { label: 'Jobs Running', value: 1, color: '#f39c12' },
  { label: 'Jobs Failed', value: 3, color: '#e74c3c' },
]

export const AWX_JOB_LOG = [
  '\x1b[36mPLAY [Deploy web tier] ******************************************\x1b[0m',
  '\x1b[36mTASK [Gathering Facts] ******************************************\x1b[0m',
  '\x1b[32mok: [web01.fixitlab.local]\x1b[0m',
  '\x1b[36mTASK [Install nginx] ********************************************\x1b[0m',
  '\x1b[32mchanged: [web01.fixitlab.local]\x1b[0m',
  '\x1b[36mTASK [Start nginx] **********************************************\x1b[0m',
  '\x1b[32mok: [web01.fixitlab.local]\x1b[0m',
  '\x1b[32mPLAY RECAP ******************************************************\x1b[0m',
  'web01.fixitlab.local : \x1b[32mok=3\x1b[0m \x1b[33mchanged=1\x1b[0m unreachable=0 failed=0',
]

export const AWX_CREDENTIAL_TYPES = [
  { id: 'machine', label: 'Machine', fields: ['username', 'password', 'ssh_key'] },
  { id: 'aws', label: 'Amazon Web Services', fields: ['access_key', 'secret_key'] },
  { id: 'github', label: 'GitHub Personal Access Token', fields: ['token'] },
  { id: 'vault', label: 'Vault', fields: ['vault_password'] },
]

export const AWX_HOSTS = [
  { id: 'h1', name: 'web01.fixitlab.local', inventory: 'Production', enabled: true, status: 'ok' },
  { id: 'h2', name: 'web02.fixitlab.local', inventory: 'Production', enabled: true, status: 'ok' },
  { id: 'h3', name: 'db01.fixitlab.local', inventory: 'Production', enabled: true, status: 'failed' },
  { id: 'h4', name: 'lab-worker-01', inventory: 'Training', enabled: true, status: 'ok' },
]

export const AWX_SCHEDULES = [
  { id: 's1', name: 'Nightly backup', template: 'DB Backup', nextRun: '2026-06-25T02:00:00Z', enabled: true },
  { id: 's2', name: 'Weekly patch', template: 'OS Patch', nextRun: '2026-06-28T04:00:00Z', enabled: true },
]

export const AWX_USERS = [
  { id: 'u1', username: 'admin', name: 'Administrator', role: 'System Admin', lastLogin: '2026-06-24T08:00:00Z' },
  { id: 'u2', username: 'awx-operator', name: 'AWX Operator', role: 'Org Admin', lastLogin: '2026-06-23T12:00:00Z' },
  { id: 'u3', username: 'labuser', name: 'Lab User', role: 'Member', lastLogin: '2026-06-22T09:30:00Z' },
]

export const AWX_ACTIVITY = [
  { id: 'a1', time: '2026-06-24T09:15:00Z', user: 'admin', action: 'Launched job template Deploy Web', object: 'Job #4412' },
  { id: 'a2', time: '2026-06-24T08:42:00Z', user: 'awx-operator', action: 'Synced project', object: 'ansible-playbooks' },
  { id: 'a3', time: '2026-06-23T16:20:00Z', user: 'labuser', action: 'Created credential', object: 'prod-ssh-key' },
  { id: 'a4', time: '2026-06-23T14:05:00Z', user: 'ci-bot', action: 'Job failed', object: 'DB Backup #4408' },
]

export const AWX_APPROVALS = [
  { id: 'ap1', workflow: 'Prod Deploy Gate', step: 'Change approval', status: 'pending', requestedBy: 'labuser', age: '2h' },
  { id: 'ap2', workflow: 'DR Failover', step: 'Manager sign-off', status: 'approved', requestedBy: 'admin', age: '1d' },
]

export const AWX_ORGANIZATIONS = [
  { id: 'o1', name: 'Default', description: 'Training organization', inventories: 4, users: 12 },
  { id: 'o2', name: 'Production Ops', description: 'Production automation', inventories: 8, users: 24 },
]

export const AWX_TEAMS = [
  { id: 't1', name: 'Platform', organization: 'Default', members: 6, role: 'Admin' },
  { id: 't2', name: 'Developers', organization: 'Default', members: 14, role: 'Execute' },
  { id: 't3', name: 'Security', organization: 'Production Ops', members: 4, role: 'Audit' },
]

export const AWX_INSTANCE_GROUPS = [
  { id: 'ig1', name: 'default', instances: 2, capacity: 100, jobsRunning: 1 },
  { id: 'ig2', name: 'isolated-prod', instances: 3, capacity: 50, jobsRunning: 0 },
]

export const AWX_EXEC_ENVS = [
  { id: 'ee1', name: 'awx-ee:latest', image: 'quay.io/ansible/awx-ee:latest', status: 'healthy' },
  { id: 'ee2', name: 'custom-network-ee', image: 'registry.fixitlab.local/ee-network:2.16', status: 'healthy' },
]

export const AWX_NOTIFICATIONS = [
  { id: 'n1', name: 'Slack Ops', type: 'Slack', destinations: '#ops-alerts', status: 'ok' },
  { id: 'n2', name: 'Email On Failure', type: 'Email', destinations: 'oncall@fixitlab.local', status: 'ok' },
  { id: 'n3', name: 'PagerDuty', type: 'PagerDuty', destinations: 'Platform rotation', status: 'disabled' },
]

export const AWX_MGMT_JOBS = [
  { id: 'mj1', name: 'Cleanup expired sessions', schedule: 'Daily 03:00', lastRun: 'Success' },
  { id: 'mj2', name: 'Remove old job artifacts', schedule: 'Weekly Sun', lastRun: 'Success' },
]

export const AWX_APPLICATIONS = [
  { id: 'app1', name: 'GitHub OAuth', clientType: 'Confidential', redirect: 'https://awx.fixitlab.local/sso/callback' },
]

export const AWX_SETTINGS_SECTIONS = {
  'settings-auth': [
    { key: 'LDAP Server URI', value: 'ldap://dc.corp.fixitlab.local' },
    { key: 'Bind DN', value: 'CN=awx-bind,OU=Service,DC=corp,DC=fixitlab,DC=local' },
    { key: 'User Search', value: '(&(objectClass=user)(sAMAccountName=%(user)s))' },
  ],
  'settings-jobs': [
    { key: 'Job timeout (seconds)', value: '3600' },
    { key: 'Concurrent jobs', value: '10' },
    { key: 'AWX task isolation', value: 'Enabled' },
  ],
  'settings-system': [
    { key: 'Base URL', value: 'https://awx.fixitlab.local' },
    { key: 'Timezone', value: 'UTC' },
    { key: 'Session timeout', value: '1800' },
  ],
  'settings-ui': [
    { key: 'Custom login info', value: 'FixitLab AWX Training' },
    { key: 'Logo', value: 'Default' },
  ],
  'settings-subscription': [
    { key: 'Subscription type', value: 'Enterprise trial' },
    { key: 'Seats', value: '50' },
    { key: 'Expires', value: '2026-12-31' },
  ],
}
