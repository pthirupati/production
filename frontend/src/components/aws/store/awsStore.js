import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'
import { useAuthStore } from '../../../store/authStore'
import {
  newInstanceId, newVolumeId, newSgId, newKeyPairId, newAmiId, newEipAllocId,
  newEipAssocId, newIamUserId, newIamRoleId, newIamGroupId, newAccessKeyId,
  newSecretAccessKey, newPrivateIp, newPublicIp, publicDns, privateDns, hostnameFromIp,
} from '../lib/ids'
import { getAmi, getInstanceType } from '../lib/instanceTypes'

const ACCOUNT_ID = '123456789012'

/** Per-user localStorage key so shared-browser / account-switch does not bleed EC2 state. */
export function awsSimStorageKey(userId) {
  return userId ? `fixitlab-aws-sim:${userId}` : 'fixitlab-aws-sim:anon'
}

function currentAwsSimStorageKey() {
  return awsSimStorageKey(useAuthStore.getState().user?.id)
}

const userScopedAwsStorage = createJSONStorage(() => ({
  getItem: () => {
    try { return localStorage.getItem(currentAwsSimStorageKey()) } catch { return null }
  },
  setItem: (_name, value) => {
    try { localStorage.setItem(currentAwsSimStorageKey(), value) } catch { /* ignore */ }
  },
  removeItem: () => {
    try { localStorage.removeItem(currentAwsSimStorageKey()) } catch { /* ignore */ }
  },
}))

export function rehydrateAwsSimForUser() {
  return useAwsStore.persist.rehydrate()
}

export function resetAwsSimOnLogout() {
  useAwsStore.getState().resetSimulation()
}

function newGenericId(service, resource) {
  const suffix = Math.random().toString(16).slice(2, 10).padEnd(8, '0')
  const shapes = {
    lambda: `fn-${suffix}`,
    rds: `db-${suffix}`,
    dynamodb: `table-${suffix}`,
    cloudformation: `stack-${suffix}`,
    route53: `Z${Math.random().toString(36).slice(2, 14).toUpperCase()}`,
    sns: `topic-${suffix}`,
    sqs: `queue-${suffix}`,
    secretsmanager: `secret-${suffix}`,
    acm: `${suffix.slice(0, 8)}-${suffix.slice(0, 4)}-${suffix.slice(4, 8)}-${suffix.slice(0, 4)}-${suffix}${suffix.slice(0, 4)}`,
    cloudfront: `E${Math.random().toString(36).slice(2, 14).toUpperCase()}`,
    eks: `cluster-${suffix}`,
    ecs: `ecs-${suffix}`,
    ecr: `repo-${suffix}`,
    apigateway: `${Math.random().toString(36).slice(2, 12)}`,
    eventbridge: `rule-${suffix}`,
    states: `sm-${suffix}`,
    kms: `${suffix.slice(0, 8)}-${suffix.slice(0, 4)}-${suffix.slice(4, 8)}-${suffix.slice(0, 4)}-${suffix}${suffix.slice(0, 4)}`,
    cloudtrail: `trail-${suffix}`,
    config: `config-rule-${suffix}`,
    systemsmanager: `param-${suffix}`,
    billing: `budget-${suffix}`,
  }
  return shapes[service] || `${service}-${resource}-${suffix}`
}

function seedGenericResources() {
  const now = '2024-03-10T14:32:01Z'
  const r = 'us-east-1'
  const row = (id, region, name, extra) => ({ id, region, name, created: now, tags: { Environment: 'demo', Project: 'fixitlab' }, ...extra })
  return {
    lambda: {
      functions: [row('fn-demo001', r, 'my-demo-function', { runtime: 'Python 3.12', memory: 128, timeout: 30, status: 'Active', handler: 'lambda_function.lambda_handler' })],
      layers: [row('layer-common001', r, 'shared-utils-layer', { runtime: 'Python 3.12', version: 3, status: 'Active' })],
    },
    rds: {
      databases: [row('db-demo001', r, 'my-demo-db', { engine: 'PostgreSQL 15.4', class: 'db.t3.micro', storage: 20, status: 'available', endpoint: 'my-demo-db.c9akciq32xze.us-east-1.rds.amazonaws.com:5432' })],
      snapshots: [row('snap-rds001', r, 'my-demo-db-snapshot', { engine: 'PostgreSQL', status: 'available' })],
    },
    dynamodb: {
      tables: [row('table-demo001', r, 'Orders', { partitionKey: 'pk (String)', sortKey: 'sk (String)', billingMode: 'On-demand', status: 'Active', items: 128 })],
    },
    cloudformation: {
      stacks: [row('stack-demo001', r, 'my-demo-stack', { status: 'CREATE_COMPLETE', resources: 4 })],
      'change-sets': [row('changeset-demo001', r, 'my-demo-stack-change-set', { status: 'CREATE_COMPLETE', changes: 2 })],
    },
    route53: {
      'hosted-zones': [row('Z1234567890ABC', '', 'example.internal', { type: 'Private', records: 7, status: 'available' })],
      'health-checks': [row('hc-demo001', '', 'api-health-check', { protocol: 'HTTPS', status: 'Healthy' })],
    },
    sns: {
      topics: [row('topic-demo001', r, 'my-alerts-topic', { type: 'Standard', subscriptions: 1, status: 'Active' })],
      subscriptions: [row('sub-demo001', r, 'admin@example.com', { protocol: 'Email', status: 'Confirmed' })],
    },
    sqs: {
      queues: [row('queue-demo001', r, 'orders-queue', { type: 'Standard', messages: 3, status: 'Active' })],
    },
    secretsmanager: {
      secrets: [row('secret-demo001', r, 'prod/db/password', { rotation: 'Disabled', lastChanged: 'Today', status: 'Active' })],
    },
    acm: {
      certificates: [row('cert-demo001', r, '*.example.com', { type: 'Amazon issued', status: 'Issued', expires: '2027-03-01' })],
    },
    cloudfront: {
      distributions: [row('E1234567890ABC', '', 'web-assets-cdn', { domainName: 'd111111abcdef8.cloudfront.net', status: 'Deployed', priceClass: 'Use all edge locations' })],
    },
    eks: {
      clusters: [row('cluster-demo001', r, 'demo-eks-cluster', { version: '1.30', nodes: 3, status: 'Active' })],
      'node-groups': [row('ng-demo001', r, 'general-workers', { instanceType: 't3.medium', desired: 3, status: 'Active' })],
    },
    ecs: {
      clusters: [row('ecscluster-demo001', r, 'default', { services: 1, tasks: 2, status: 'Active' })],
      services: [row('ecsservice-demo001', r, 'web-service', { desired: 2, running: 2, status: 'Active' })],
      tasks: [row('ecstask-demo001', r, 'web-task', { launchType: 'FARGATE', status: 'RUNNING' })],
    },
    ecr: {
      repositories: [row('repo-demo001', r, 'web-app', { images: 3, scanOnPush: 'Enabled', status: 'Active' })],
    },
    apigateway: {
      apis: [row('a1b2c3d4e5', r, 'orders-api', { type: 'HTTP', stage: 'prod', status: 'Active' })],
    },
    eventbridge: {
      rules: [row('rule-demo001', r, 'nightly-maintenance', { eventBus: 'default', targets: 1, status: 'Enabled' })],
    },
    states: {
      'state-machines': [row('sm-demo001', r, 'order-workflow', { type: 'STANDARD', executions: 12, status: 'Active' })],
    },
    kms: {
      keys: [row('key-demo001', r, 'alias/app-key', { usage: 'Encrypt and decrypt', rotation: 'Enabled', status: 'Enabled' })],
    },
    cloudtrail: {
      trails: [row('trail-demo001', r, 'organization-trail', { multiRegion: 'Yes', logging: 'On', status: 'Active' })],
    },
    config: {
      rules: [row('config-rule-demo001', r, 's3-bucket-public-read-prohibited', { compliance: 'COMPLIANT', evaluations: 24, status: 'Active' })],
    },
    systemsmanager: {
      parameters: [row('param-demo001', r, '/app/prod/api-url', { type: 'String', tier: 'Standard', status: 'Active' })],
    },
    billing: {
      budgets: [row('budget-demo001', '', 'Monthly engineering budget', { amount: 100, actual: 47.32, status: 'OK' })],
    },
    waf: {
      'web-acls': [row('waf-demo001', r, 'app-web-acl', { scope: 'Regional', rules: 3, status: 'Active' })],
    },
    cognito: {
      'user-pools': [row('us-east-1_demoPool', r, 'customers', { users: 24, mfa: 'Optional', status: 'Enabled' })],
    },
    elasticache: {
      clusters: [row('cache-demo001', r, 'app-cache', { engine: 'Redis OSS', nodes: 2, status: 'available' })],
    },
    redshift: {
      clusters: [row('redshift-demo001', r, 'analytics-warehouse', { nodeType: 'ra3.xlplus', nodes: 2, status: 'available' })],
    },
    opensearch: {
      domains: [row('os-demo001', r, 'logs-search', { version: 'OpenSearch 2.13', nodes: 3, status: 'Active' })],
    },
    kinesis: {
      streams: [row('kinesis-demo001', r, 'orders-stream', { mode: 'On-demand', shards: 4, status: 'Active' })],
    },
    glue: {
      jobs: [row('glue-job-demo001', r, 'daily-partition-loader', { type: 'Spark', runs: 8, status: 'Active' })],
      databases: [row('glue-db-demo001', r, 'lakehouse', { tables: 6, status: 'Active' })],
    },
    athena: {
      workgroups: [row('athena-demo001', r, 'primary', { queries: 18, bytesScanned: '1.2 GB', status: 'Enabled' })],
    },
    codecommit: {
      repositories: [row('repo-code-demo001', r, 'platform-infra', { defaultBranch: 'main', commits: 42, status: 'Active' })],
    },
    codebuild: {
      projects: [row('build-demo001', r, 'frontend-build', { environment: 'Linux container', lastBuild: 'SUCCEEDED', status: 'Active' })],
    },
    codepipeline: {
      pipelines: [row('pipeline-demo001', r, 'prod-deploy', { stages: 3, lastExecution: 'Succeeded', status: 'Active' })],
    },
    organizations: {
      accounts: [row('123456789012', '', 'Management account', { email: 'admin@example.com', ou: 'Root', status: 'ACTIVE' })],
    },
    servicequotas: {
      requests: [row('quota-demo001', r, 'Running On-Demand Standard instances', { service: 'EC2', requested: 64, status: 'CASE_OPENED' })],
    },
    health: {
      events: [row('event-demo001', r, 'No open issues', { service: 'All services', impact: 'Informational', status: 'closed' })],
    },
    trustedadvisor: {
      checks: [row('ta-demo001', '', 'Security groups unrestricted access', { category: 'Security', affected: 0, status: 'OK' })],
    },
    wellarchitected: {
      workloads: [row('wa-demo001', r, 'fixitlab-production', { lenses: 'AWS Well-Architected Framework', risks: 2, status: 'Active' })],
    },
  }
}

// ---------- Seed data ----------
function seedState() {
  return {
    account: {
      id: ACCOUNT_ID,
      alias: 'my-aws-simulation',
      email: 'admin@example.com',
      rootEmail: 'root@example.com',
    },
    region: 'us-east-1',
    darkMode: false,

    vpcs: [
      { id: 'vpc-0a1b2c3d4e5f67890', region: 'us-east-1', name: '', cidr: '172.31.0.0/16', state: 'available', isDefault: true, dnsHostnames: true, dnsSupport: true, tenancy: 'default' },
    ],
    subnets: [
      { id: 'subnet-0a1b2c3d4e5f10001', region: 'us-east-1', vpcId: 'vpc-0a1b2c3d4e5f67890', cidr: '172.31.0.0/20', az: 'us-east-1a', availableIps: 4091, mapPublicIp: true, isDefault: true },
      { id: 'subnet-0a1b2c3d4e5f10002', region: 'us-east-1', vpcId: 'vpc-0a1b2c3d4e5f67890', cidr: '172.31.16.0/20', az: 'us-east-1b', availableIps: 4091, mapPublicIp: true, isDefault: true },
      { id: 'subnet-0a1b2c3d4e5f10003', region: 'us-east-1', vpcId: 'vpc-0a1b2c3d4e5f67890', cidr: '172.31.32.0/20', az: 'us-east-1c', availableIps: 4091, mapPublicIp: true, isDefault: true },
    ],
    internetGateways: [
      { id: 'igw-0a1b2c3d4e5f67891', region: 'us-east-1', vpcId: 'vpc-0a1b2c3d4e5f67890', state: 'attached', name: '' },
    ],
    routeTables: [
      { id: 'rtb-0a1b2c3d4e5f67892', region: 'us-east-1', vpcId: 'vpc-0a1b2c3d4e5f67890', main: true, routes: [{ dest: '172.31.0.0/16', target: 'local' }, { dest: '0.0.0.0/0', target: 'igw-0a1b2c3d4e5f67891' }] },
    ],
    securityGroups: [
      { id: 'sg-0a1b2c3web00001', region: 'us-east-1', name: 'web-sg', description: 'Allow web traffic', vpcId: 'vpc-0a1b2c3d4e5f67890', inbound: [
        { id: 'sgr-1', type: 'SSH', protocol: 'TCP', from: 22, to: 22, source: '0.0.0.0/0', description: 'SSH' },
        { id: 'sgr-2', type: 'HTTP', protocol: 'TCP', from: 80, to: 80, source: '0.0.0.0/0', description: 'HTTP' },
        { id: 'sgr-3', type: 'HTTPS', protocol: 'TCP', from: 443, to: 443, source: '0.0.0.0/0', description: 'HTTPS' },
      ], outbound: [{ id: 'sgr-o1', type: 'All traffic', protocol: 'All', from: 0, to: 65535, source: '0.0.0.0/0', description: '' }] },
      { id: 'sg-0a1b2c3db000002', region: 'us-east-1', name: 'db-sg', description: 'Database access', vpcId: 'vpc-0a1b2c3d4e5f67890', inbound: [
        { id: 'sgr-4', type: 'MySQL/Aurora', protocol: 'TCP', from: 3306, to: 3306, source: 'sg-0a1b2c3web00001', description: 'MySQL from web' },
        { id: 'sgr-5', type: 'PostgreSQL', protocol: 'TCP', from: 5432, to: 5432, source: 'sg-0a1b2c3web00001', description: 'PG from web' },
      ], outbound: [{ id: 'sgr-o2', type: 'All traffic', protocol: 'All', from: 0, to: 65535, source: '0.0.0.0/0', description: '' }] },
      { id: 'sg-0a1b2c3default03', region: 'us-east-1', name: 'default', description: 'default VPC security group', vpcId: 'vpc-0a1b2c3d4e5f67890', inbound: [{ id: 'sgr-d', type: 'All traffic', protocol: 'All', from: 0, to: 65535, source: 'self', description: '' }], outbound: [{ id: 'sgr-od', type: 'All traffic', protocol: 'All', from: 0, to: 65535, source: '0.0.0.0/0', description: '' }] },
    ],
    keyPairs: [
      { id: 'key-0aa11demo000001', region: 'us-east-1', name: 'demo-key-pair', type: 'rsa', fingerprint: 'a1:b2:c3:d4:e5:f6:01:02:03:04:05:06:07:08:09:0a', created: '2024-01-15T09:00:00Z' },
      { id: 'key-0bb22prod000002', region: 'us-east-1', name: 'production-key', type: 'ed25519', fingerprint: 'SHA256:Zm9vYmFyMTIzNDU2Nzg5MGFiY2RlZmdoaWprbA', created: '2024-02-20T11:30:00Z' },
    ],
    volumes: [
      { id: 'vol-0abc123def456789a', region: 'us-east-1', size: 8, type: 'gp3', state: 'in-use', az: 'us-east-1a', encrypted: true, attachedTo: 'i-0abc123def4567890', device: '/dev/xvda', created: '2024-01-15T09:00:00Z' },
      { id: 'vol-0def456abc789012b', region: 'us-east-1', size: 20, type: 'gp3', state: 'in-use', az: 'us-east-1b', encrypted: false, attachedTo: 'i-0def456abc7890123', device: '/dev/xvda', created: '2024-01-16T09:00:00Z' },
      { id: 'vol-0ghi789jkl012345c', region: 'us-east-1', size: 20, type: 'gp3', state: 'in-use', az: 'us-east-1c', encrypted: false, attachedTo: 'i-0ghi789jkl0123456', device: '/dev/xvda', created: '2024-01-17T09:00:00Z' },
      { id: 'vol-0jkl012mno345678d', region: 'us-east-1', size: 50, type: 'gp3', state: 'available', az: 'us-east-1a', encrypted: false, attachedTo: null, device: null, created: '2024-02-01T09:00:00Z' },
    ],
    amis: [
      { id: 'ami-0custom00web0001', region: 'us-east-1', name: 'my-web-server-ami', os: 'amazon-linux-2023', platform: 'Linux/UNIX', arch: 'x86_64', user: 'ec2-user', desc: 'Created from web-server-01', owner: ACCOUNT_ID, created: '2024-03-01T09:00:00Z', visibility: 'private' },
      { id: 'ami-0custom00db00002', region: 'us-east-1', name: 'my-db-server-ami', os: 'ubuntu-22.04', platform: 'Ubuntu', arch: 'x86_64', user: 'ubuntu', desc: 'Created from db-server-01', owner: ACCOUNT_ID, created: '2024-03-01T09:00:00Z', visibility: 'private' },
    ],
    elasticIps: [
      { allocationId: 'eipalloc-0abc123def4567a', region: 'us-east-1', publicIp: '54.210.123.45', associationId: 'eipassoc-0abc123def4567b', instanceId: 'i-0abc123def4567890', domain: 'vpc' },
    ],
    instances: [
      {
        id: 'i-0abc123def4567890', region: 'us-east-1', name: 'web-server-01', state: 'running',
        amiId: 'ami-0c02fb55956c7d316', os: 'amazon-linux-2023', type: 't2.micro', az: 'us-east-1a',
        subnetId: 'subnet-0a1b2c3d4e5f10001', vpcId: 'vpc-0a1b2c3d4e5f67890',
        publicIp: '54.210.123.45', privateIp: '172.31.14.52', keyName: 'demo-key-pair',
        securityGroups: ['sg-0a1b2c3web00001'], iamRole: 'EC2InstanceRole', monitoring: 'disabled',
        rootDevice: '/dev/xvda', rootVolume: 'vol-0abc123def456789a', launchTime: '2024-01-15T09:00:12Z',
        statusChecks: '2/2', tenancy: 'default', architecture: 'x86_64',
        tags: { Name: 'web-server-01', Environment: 'demo', Project: 'fixitlab' },
      },
      {
        id: 'i-0def456abc7890123', region: 'us-east-1', name: 'db-server-01', state: 'running',
        amiId: 'ami-0557a15b87f6559cf', os: 'ubuntu-22.04', type: 't3.small', az: 'us-east-1b',
        subnetId: 'subnet-0a1b2c3d4e5f10002', vpcId: 'vpc-0a1b2c3d4e5f67890',
        publicIp: '', privateIp: '172.31.28.33', keyName: 'demo-key-pair',
        securityGroups: ['sg-0a1b2c3db000002'], iamRole: '', monitoring: 'disabled',
        rootDevice: '/dev/xvda', rootVolume: 'vol-0def456abc789012b', launchTime: '2024-01-16T10:22:00Z',
        statusChecks: '2/2', tenancy: 'default', architecture: 'x86_64',
        tags: { Name: 'db-server-01', Environment: 'demo' },
      },
      {
        id: 'i-0ghi789jkl0123456', region: 'us-east-1', name: 'app-server-01', state: 'stopped',
        amiId: 'ami-026ebd4cfe2c043b2', os: 'rhel-9', type: 't3.medium', az: 'us-east-1c',
        subnetId: 'subnet-0a1b2c3d4e5f10003', vpcId: 'vpc-0a1b2c3d4e5f67890',
        publicIp: '', privateIp: '172.31.42.11', keyName: 'demo-key-pair',
        securityGroups: ['sg-0a1b2c3web00001'], iamRole: '', monitoring: 'disabled',
        rootDevice: '/dev/xvda', rootVolume: 'vol-0ghi789jkl012345c', launchTime: '2024-02-10T08:00:00Z',
        statusChecks: '0/2', tenancy: 'default', architecture: 'x86_64',
        tags: { Name: 'app-server-01' },
      },
    ],

    s3Buckets: [
      {
        name: 'my-web-assets-demo-123456', region: 'us-east-1', created: '2024-01-10T09:00:00Z',
        versioning: true, publicAccess: 'Objects can be public', encryption: 'SSE-S3', website: true,
        objects: [
          { key: 'index.html', size: 4302, modified: '2024-03-01T10:00:00Z', storageClass: 'STANDARD' },
          { key: 'style.css', size: 8112, modified: '2024-03-01T10:00:00Z', storageClass: 'STANDARD' },
          { key: 'script.js', size: 15334, modified: '2024-03-01T10:00:00Z', storageClass: 'STANDARD' },
          { key: 'logo.svg', size: 2150, modified: '2024-03-01T10:00:00Z', storageClass: 'STANDARD' },
          { key: 'robots.txt', size: 100, modified: '2024-03-01T10:00:00Z', storageClass: 'STANDARD' },
          { key: 'images/hero.jpg', size: 251000, modified: '2024-03-01T10:00:00Z', storageClass: 'STANDARD' },
        ],
      },
      {
        name: 'my-backups-demo-123456', region: 'us-east-1', created: '2024-01-12T09:00:00Z',
        versioning: true, publicAccess: 'Bucket and objects not public', encryption: 'SSE-S3', website: false,
        objects: [
          { key: 'backups/2024-03-01/db.tar.gz', size: 10485760, modified: '2024-03-01T03:00:00Z', storageClass: 'STANDARD_IA' },
          { key: 'backups/2024-03-01/files.tar.gz', size: 5242880, modified: '2024-03-01T03:00:00Z', storageClass: 'STANDARD_IA' },
        ],
      },
      {
        name: 'my-logs-demo-123456', region: 'us-east-1', created: '2024-01-12T09:00:00Z',
        versioning: false, publicAccess: 'Bucket and objects not public', encryption: 'SSE-S3', website: false,
        objects: [],
      },
    ],

    iamUsers: [
      { id: newIamUserId(), name: 'admin-user', created: '2024-01-05T09:00:00Z', consoleAccess: true, groups: ['Administrators'], policies: ['AdministratorAccess'], accessKeys: [] },
      { id: newIamUserId(), name: 'developer-user', created: '2024-01-06T09:00:00Z', consoleAccess: true, groups: ['Developers'], policies: ['PowerUserAccess'], accessKeys: [{ id: 'AKIAIOSFODNN7EXAMPLE', created: '2024-01-06T09:05:00Z', status: 'Active', lastUsed: '2024-03-10' }] },
      { id: newIamUserId(), name: 'readonly-user', created: '2024-01-07T09:00:00Z', consoleAccess: true, groups: ['ReadOnly'], policies: ['ReadOnlyAccess'], accessKeys: [] },
    ],
    iamGroups: [
      { id: newIamGroupId(), name: 'Administrators', created: '2024-01-05T09:00:00Z', users: ['admin-user'], policies: ['AdministratorAccess'] },
      { id: newIamGroupId(), name: 'Developers', created: '2024-01-05T09:00:00Z', users: ['developer-user'], policies: ['PowerUserAccess'] },
      { id: newIamGroupId(), name: 'ReadOnly', created: '2024-01-05T09:00:00Z', users: ['readonly-user'], policies: ['ReadOnlyAccess'] },
    ],
    iamRoles: [
      { id: newIamRoleId(), name: 'EC2InstanceRole', created: '2024-01-05T09:00:00Z', trustedEntity: 'ec2.amazonaws.com', policies: ['AmazonS3ReadOnlyAccess', 'CloudWatchAgentServerPolicy'] },
      { id: newIamRoleId(), name: 'LambdaExecutionRole', created: '2024-01-05T09:00:00Z', trustedEntity: 'lambda.amazonaws.com', policies: ['AWSLambdaBasicExecutionRole'] },
      { id: newIamRoleId(), name: 'EKSClusterRole', created: '2024-01-05T09:00:00Z', trustedEntity: 'eks.amazonaws.com', policies: ['AmazonEKSClusterPolicy'] },
      { id: newIamRoleId(), name: 'EKSNodeRole', created: '2024-01-05T09:00:00Z', trustedEntity: 'ec2.amazonaws.com', policies: ['AmazonEKSWorkerNodePolicy', 'AmazonEKS_CNI_Policy', 'AmazonEC2ContainerRegistryReadOnly'] },
      { id: newIamRoleId(), name: 'CloudFormationRole', created: '2024-01-05T09:00:00Z', trustedEntity: 'cloudformation.amazonaws.com', policies: ['PowerUserAccess'] },
    ],
    iamPolicies: [
      { name: 'MyS3BucketPolicy', type: 'Customer managed', attached: 1, created: '2024-01-20T09:00:00Z', description: 'Allows access to a specific S3 bucket', document: { Version: '2012-10-17', Statement: [{ Effect: 'Allow', Action: ['s3:GetObject', 's3:PutObject'], Resource: 'arn:aws:s3:::my-web-assets-demo-123456/*' }] } },
      { name: 'MyEC2Policy', type: 'Customer managed', attached: 0, created: '2024-01-20T09:00:00Z', description: 'EC2 read + start/stop for tagged resources', document: { Version: '2012-10-17', Statement: [{ Effect: 'Allow', Action: ['ec2:Describe*', 'ec2:StartInstances', 'ec2:StopInstances'], Resource: '*' }] } },
      { name: 'MyDeveloperPolicy', type: 'Customer managed', attached: 1, created: '2024-01-20T09:00:00Z', description: 'Broad dev access excluding IAM/billing', document: { Version: '2012-10-17', Statement: [{ Effect: 'Allow', NotAction: ['iam:*', 'organizations:*', 'account:*'], Resource: '*' }] } },
    ],

    cwAlarms: [
      { name: 'HighCPUUtilization', region: 'us-east-1', metric: 'CPUUtilization', namespace: 'AWS/EC2', state: 'OK', threshold: '> 80% for 2/3 datapoints' },
      { name: 'DiskSpaceLow', region: 'us-east-1', metric: 'disk_used_percent', namespace: 'CWAgent', state: 'OK', threshold: '> 85%' },
      { name: 'LambdaErrors', region: 'us-east-1', metric: 'Errors', namespace: 'AWS/Lambda', state: 'OK', threshold: '> 0 for 1/1' },
    ],

    genericResources: seedGenericResources(),

    flash: [], // {id, type, message}
    labManagedIds: [], // instance/bucket ids created during an active lab session
  }
}

let flashSeq = 1

export const useAwsStore = create(
  persist(
    (set, get) => ({
      ...seedState(),

      // ---------- Flash messages ----------
      pushFlash: (type, message) => {
        const id = flashSeq += 1
        set((s) => ({ flash: [...(s.flash || []), { id, type, message }] }))
        if (type === 'success' || type === 'info') {
          setTimeout(() => get().dismissFlash(id), 8000)
        }
        return id
      },
      dismissFlash: (id) => set((s) => ({ flash: (s.flash || []).filter((f) => f.id !== id) })),

      // ---------- Account / region ----------
      setRegion: (region) => set({ region }),
      toggleDarkMode: () => set((s) => ({ darkMode: !s.darkMode })),
      resetSimulation: () => set({ ...seedState() }),

      markLabManaged: (ids) => set((s) => ({
        labManagedIds: [...new Set([...(s.labManagedIds || []), ...(ids || [])])],
      })),

      resetLabManaged: () => {
        const { labManagedIds = [], instances, s3Buckets, securityGroups } = get()
        if (!labManagedIds.length) return
        const instIds = labManagedIds.filter((x) => x.startsWith('i-'))
        const bucketNames = labManagedIds.filter((x) => x.startsWith('bucket:')).map((x) => x.slice(7))
        const sgNames = labManagedIds.filter((x) => x.startsWith('sg:')).map((x) => x.slice(3))
        set({
          instances: instances.filter((i) => !instIds.includes(i.id)),
          s3Buckets: s3Buckets.filter((b) => !bucketNames.includes(b.name)),
          securityGroups: securityGroups.filter((sg) => !sgNames.includes(sg.name)),
          labManagedIds: [],
        })
      },

      // ---------- EC2 instances ----------
      launchInstances: ({ name, amiId, type, count, keyName, subnetId, securityGroups, volumeSize, volumeType, monitoring, tags }) => {
        const { region, subnets } = get()
        const ami = getAmi(amiId)
        const subnet = subnets.find((sn) => sn.id === subnetId) || subnets.find((sn) => sn.region === region)
        const az = subnet?.az || `${region}a`
        const created = []
        for (let i = 0; i < count; i += 1) {
          const id = newInstanceId()
          const privateIp = newPrivateIp(subnet ? subnet.cidr.split('/')[0] : '172.31.16.0')
          const publicIp = subnet?.mapPublicIp ? newPublicIp() : ''
          const rootVol = newVolumeId()
          const instanceName = count > 1 ? `${name || ''}` : (name || '')
          created.push({
            id, region, name: instanceName, state: 'pending', amiId, os: ami.os, type, az,
            subnetId: subnet?.id || '', vpcId: subnet?.vpcId || '',
            publicIp, privateIp, keyName: keyName || '', securityGroups, iamRole: '',
            monitoring: monitoring ? 'enabled' : 'disabled', rootDevice: '/dev/xvda', rootVolume: rootVol,
            launchTime: new Date().toISOString(), statusChecks: 'initializing', tenancy: 'default',
            architecture: getInstanceType(type).arch,
            workload: ami.workload || 'linux',
            tags: { ...(name ? { Name: name } : {}), ...(tags || {}) },
          })
          set((s) => ({
            volumes: [...s.volumes, { id: rootVol, region, size: volumeSize || 8, type: volumeType || 'gp3', state: 'in-use', az, encrypted: false, attachedTo: id, device: '/dev/xvda', created: new Date().toISOString() }],
          }))
        }
        set((s) => ({ instances: [...s.instances, ...created] }))
        // pending -> running after a short delay (status checks)
        created.forEach((inst) => {
          setTimeout(() => {
            set((s) => ({ instances: s.instances.map((x) => (x.id === inst.id ? { ...x, state: 'running', statusChecks: '2/2' } : x)) }))
          }, 4000 + Math.random() * 2000)
        })
        return created
      },

      instanceAction: (ids, action) => {
        const transitions = {
          start: { interim: 'pending', final: 'running' },
          stop: { interim: 'stopping', final: 'stopped' },
          reboot: { interim: 'rebooting', final: 'running' },
          terminate: { interim: 'shutting-down', final: 'terminated' },
        }
        const t = transitions[action]
        if (!t) return
        set((s) => ({ instances: s.instances.map((x) => (ids.includes(x.id) ? { ...x, state: t.interim, statusChecks: action === 'stop' || action === 'terminate' ? '-' : 'initializing' } : x)) }))
        setTimeout(() => {
          set((s) => ({
            instances: s.instances.map((x) => {
              if (!ids.includes(x.id)) return x
              if (action === 'terminate') return { ...x, state: 'terminated', statusChecks: '-', publicIp: '' }
              if (action === 'stop') return { ...x, state: 'stopped', statusChecks: '-', publicIp: x.publicIp }
              return { ...x, state: t.final, statusChecks: '2/2' }
            }),
          }))
        }, 3000)
      },

      setInstanceName: (id, name) => set((s) => ({
        instances: s.instances.map((x) => (x.id === id ? { ...x, name, tags: { ...x.tags, Name: name } } : x)),
      })),

      // ---------- Key pairs ----------
      createKeyPair: ({ name, type }) => {
        const { region } = get()
        const kp = { id: newKeyPairId(), region, name, type: type || 'rsa', fingerprint: Array.from({ length: 16 }, () => Math.floor(Math.random() * 256).toString(16).padStart(2, '0')).join(':'), created: new Date().toISOString() }
        set((s) => ({ keyPairs: [...s.keyPairs, kp] }))
        return kp
      },
      deleteKeyPair: (name) => set((s) => ({ keyPairs: s.keyPairs.filter((k) => k.name !== name) })),

      // ---------- Security groups ----------
      createSecurityGroup: ({ name, description, vpcId, inbound }) => {
        const { region } = get()
        const sg = { id: newSgId(), region, name, description, vpcId, inbound: inbound || [], outbound: [{ id: 'sgr-o', type: 'All traffic', protocol: 'All', from: 0, to: 65535, source: '0.0.0.0/0', description: '' }] }
        set((s) => ({ securityGroups: [...s.securityGroups, sg] }))
        return sg
      },

      // ---------- Elastic IPs ----------
      allocateEip: () => {
        const { region } = get()
        const eip = { allocationId: newEipAllocId(), region, publicIp: newPublicIp(), associationId: null, instanceId: null, domain: 'vpc' }
        set((s) => ({ elasticIps: [...s.elasticIps, eip] }))
        return eip
      },
      releaseEip: (allocationId) => set((s) => ({ elasticIps: s.elasticIps.filter((e) => e.allocationId !== allocationId) })),

      // ---------- S3 ----------
      createBucket: ({ name, region, versioning, encryption, blockPublic }) => {
        const bucket = {
          name,
          region: region || get().region,
          created: new Date().toISOString(),
          versioning: !!versioning,
          publicAccess: blockPublic ? 'Bucket and objects not public' : 'Objects can be public',
          encryption: encryption || 'SSE-S3',
          website: false,
          objectOwnership: 'Bucket owner enforced',
          acl: 'Private',
          bucketPolicy: '',
          cors: '',
          lifecycleRules: [],
          logging: false,
          objects: [],
        }
        set((s) => ({ s3Buckets: [...s.s3Buckets, bucket] }))
        return bucket
      },
      deleteBucket: (name) => set((s) => ({ s3Buckets: s.s3Buckets.filter((b) => b.name !== name) })),
      updateBucket: (name, patch) => set((s) => ({
        s3Buckets: s.s3Buckets.map((b) => (b.name === name ? { ...b, ...patch } : b)),
      })),
      putObject: (bucketName, key, size) => set((s) => ({
        s3Buckets: s.s3Buckets.map((b) => (b.name === bucketName ? { ...b, objects: [...b.objects.filter((o) => o.key !== key), { key, size: size || 0, modified: new Date().toISOString(), storageClass: 'STANDARD', etag: `"${Math.random().toString(16).slice(2, 34).padEnd(32, '0')}"` }] } : b)),
      })),
      deleteObject: (bucketName, key) => set((s) => ({
        s3Buckets: s.s3Buckets.map((b) => (b.name === bucketName ? { ...b, objects: b.objects.filter((o) => o.key !== key) } : b)),
      })),

      // ---------- IAM ----------
      createIamUser: ({ name, consoleAccess, policies }) => {
        const user = { id: newIamUserId(), name, created: new Date().toISOString(), consoleAccess: !!consoleAccess, groups: [], policies: policies || [], accessKeys: [] }
        set((s) => ({ iamUsers: [...s.iamUsers, user] }))
        return user
      },
      deleteIamUser: (name) => set((s) => ({ iamUsers: s.iamUsers.filter((u) => u.name !== name) })),
      createAccessKey: (userName) => {
        const key = { id: newAccessKeyId(), secret: newSecretAccessKey(), created: new Date().toISOString(), status: 'Active', lastUsed: 'N/A' }
        set((s) => ({ iamUsers: s.iamUsers.map((u) => (u.name === userName ? { ...u, accessKeys: [...u.accessKeys, { id: key.id, created: key.created, status: 'Active', lastUsed: 'N/A' }] } : u)) }))
        return key
      },
      createIamRole: ({ name, trustedEntity, policies }) => {
        const role = { id: newIamRoleId(), name, created: new Date().toISOString(), trustedEntity, policies: policies || [] }
        set((s) => ({ iamRoles: [...s.iamRoles, role] }))
        return role
      },
      createIamPolicy: ({ name, description, document }) => {
        const policy = { name, type: 'Customer managed', attached: 0, created: new Date().toISOString(), description, document }
        set((s) => ({ iamPolicies: [...s.iamPolicies, policy] }))
        return policy
      },
      updateIamPolicy: (name, patch) => set((s) => ({
        iamPolicies: s.iamPolicies.map((p) => (p.name === name ? { ...p, ...patch } : p)),
      })),
      deleteIamPolicy: (name) => set((s) => ({ iamPolicies: s.iamPolicies.filter((p) => p.name !== name) })),

      // ---------- Generic services ----------
      createGenericResource: (service, resource, payload) => {
        const { region } = get()
        const created = {
          id: newGenericId(service, resource),
          region,
          created: new Date().toISOString(),
          tags: { Environment: 'demo', Project: 'fixitlab' },
          status: 'Active',
          ...payload,
        }
        set((s) => ({
          genericResources: {
            ...(s.genericResources || {}),
            [service]: {
              ...(s.genericResources?.[service] || {}),
              [resource]: [...(s.genericResources?.[service]?.[resource] || []), created],
            },
          },
        }))
        return created
      },
      deleteGenericResource: (service, resource, id) => set((s) => ({
        genericResources: {
          ...(s.genericResources || {}),
          [service]: {
            ...(s.genericResources?.[service] || {}),
            [resource]: (s.genericResources?.[service]?.[resource] || []).filter((x) => x.id !== id),
          },
        },
      })),
      updateGenericResource: (service, resource, id, patch) => set((s) => ({
        genericResources: {
          ...(s.genericResources || {}),
          [service]: {
            ...(s.genericResources?.[service] || {}),
            [resource]: (s.genericResources?.[service]?.[resource] || []).map((x) => (x.id === id ? { ...x, ...patch } : x)),
          },
        },
      })),
    }),
    {
      name: 'fixitlab-aws-sim',
      storage: userScopedAwsStorage,
      version: 2,
      // Persist resource state + region, but not transient flash messages.
      partialize: (s) => {
        const { flash, ...rest } = s
        return rest
      },
      merge: (persisted, current) => {
        const seed = seedState()
        const p = persisted || {}
        const merged = { ...current, ...p, flash: [] }
        merged.account = { ...seed.account, ...(p.account || {}) }
        merged.region = p.region || current.region || seed.region
        merged.darkMode = p.darkMode ?? current.darkMode ?? false
        for (const key of Object.keys(seed)) {
          if (key === 'account' || key === 'region' || key === 'darkMode' || key === 'flash') continue
          if (key === 'genericResources') {
            merged.genericResources = p.genericResources && typeof p.genericResources === 'object'
              ? { ...seed.genericResources, ...p.genericResources }
              : seed.genericResources
            continue
          }
          if (Array.isArray(seed[key])) {
            merged[key] = Array.isArray(p[key]) ? p[key] : seed[key]
          }
        }
        return merged
      },
    },
  ),
)

// ---------- Region-scoped selectors ----------
export const ACCOUNT = ACCOUNT_ID
export const scoped = (arr, region) => (arr || []).filter((x) => !x.region || x.region === region)
