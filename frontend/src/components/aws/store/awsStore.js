import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'
import { useAuthStore } from '../../../store/authStore'
import {
  newInstanceId, newVolumeId, newSnapshotId, newSgId, newKeyPairId, newAmiId, newEipAllocId,
  newEipAssocId, newIgwId, newSubnetId, newVpcId, newSgRuleId, newRtbId, newNatId, newAclId,
  newIamUserId, newIamRoleId, newIamGroupId, newAccessKeyId,
  newSecretAccessKey, newPrivateIp, newPublicIp, publicDns, privateDns, hostnameFromIp,
} from '../lib/ids'
import { getAmi, getInstanceType } from '../lib/instanceTypes'
import {
  EC2_TIMING, GENERIC_TIMING, dueIn,
  initializingChecks, phase1Checks, passedChecks, noChecks,
  armLifecycleTick,
} from '../lib/lifecycle'
import {
  dependencyViolation, invalidGroupInUse, invalidParameterValue,
  bucketNotEmpty, malformedPolicyDocument, resourceNotFound,
  operationNotPermitted, fail, ok,
} from '../lib/errors'
import { evaluate, policiesFromNames } from '../lib/iamEngine'
import {
  isValidCidr, isValidBucketName, isValidPolicyJson,
  cidrWithinVpc, cidrsOverlap, duplicateSgNameInVpc,
} from '../lib/validators'
import { SERVICE_CONFIGS } from '../pages/generic/serviceConfigs'
import { awsSimApi } from '../../../api/awsSim'
import { notifyAwsBridge } from '../../../api/awsBridge'

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

/**
 * Hard reset used by the lab error-boundary "Reset saved state" action: wipe the
 * persisted blob for the current user AND re-seed the live in-memory store so a
 * corrupt/old payload can neither rehydrate again nor keep crashing the mount.
 * Also sweeps legacy / other-user aws sim keys so a stale blob under a different
 * key cannot keep poisoning the console after login switches.
 * Every step is independently guarded so the recovery path itself never throws.
 */
export function hardResetAwsSim() {
  try {
    const keys = []
    for (let i = 0; i < localStorage.length; i += 1) {
      const k = localStorage.key(i)
      if (k && (k === 'fixitlab-aws-sim' || k.startsWith('fixitlab-aws-sim:'))) keys.push(k)
    }
    keys.forEach((k) => {
      try { localStorage.removeItem(k) } catch { /* ignore */ }
    })
  } catch { /* ignore */ }
  try { localStorage.removeItem(currentAwsSimStorageKey()) } catch { /* ignore */ }
  try { useAwsStore.getState().resetSimulation() } catch { /* ignore */ }
  try { useAwsStore.getState()._ensureTick() } catch { /* ignore */ }
  try { useAwsStore.getState().disarmLabSync() } catch { /* ignore */ }
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
  const row = (id, region, name, extra) => ({ id, region, name, created: now, tags: { Environment: 'lab', Project: 'fixitlab' }, ...extra })
  return {
    lambda: {
      functions: [row('fn-lab001', r, 'my-lab-function', {
        runtime: 'Python 3.12', memory: 128, timeout: 30, status: 'Active', handler: 'lambda_function.lambda_handler',
        code: 'def lambda_handler(event, context):\n    return {"statusCode": 200, "body": "Hello from Lambda!"}',
        env: { STAGE: 'prod', LOG_LEVEL: 'INFO' },
        triggers: [{ type: 'API Gateway', detail: 'orders-api / ANY /orders' }],
        invocationHistory: [
          { at: '2024-03-10T14:00:00Z', statusCode: 200, durationMs: 182, billedMs: 200, memoryUsed: 74 },
          { at: '2024-03-10T13:55:00Z', statusCode: 200, durationMs: 205, billedMs: 300, memoryUsed: 78 },
        ],
      })],
      layers: [row('layer-common001', r, 'shared-utils-layer', { runtime: 'Python 3.12', version: 3, status: 'Active' })],
    },
    rds: {
      databases: [row('db-lab001', r, 'my-lab-db', { engine: 'PostgreSQL 15.4', class: 'db.t3.micro', storage: 20, multiAz: false, status: 'available', endpoint: 'my-lab-db.c9akciq32xze.us-east-1.rds.amazonaws.com:5432' })],
      snapshots: [row('snap-rds001', r, 'my-lab-db-snapshot', { engine: 'PostgreSQL', status: 'available' })],
    },
    dynamodb: {
      tables: [row('table-demo001', r, 'Orders', {
        partitionKey: 'pk (String)', sortKey: 'sk (String)', billingMode: 'On-demand', status: 'Active', items: 3,
        records: [
          { pk: 'ORDER#1001', sk: 'META', customer: 'acme-corp', total: 249.99, status: 'shipped' },
          { pk: 'ORDER#1002', sk: 'META', customer: 'globex', total: 89.5, status: 'pending' },
          { pk: 'ORDER#1003', sk: 'META', customer: 'initech', total: 1299.0, status: 'delivered' },
        ],
      })],
    },
    cloudformation: {
      stacks: [row('stack-lab001', r, 'my-lab-stack', {
        status: 'CREATE_COMPLETE', resources: 4,
        events: [
          { at: '2024-03-10T14:30:00Z', logicalId: 'my-lab-stack', type: 'AWS::CloudFormation::Stack', status: 'CREATE_COMPLETE', reason: '' },
          { at: '2024-03-10T14:29:40Z', logicalId: 'AppSecurityGroup', type: 'AWS::EC2::SecurityGroup', status: 'CREATE_COMPLETE', reason: '' },
          { at: '2024-03-10T14:29:20Z', logicalId: 'AppBucket', type: 'AWS::S3::Bucket', status: 'CREATE_COMPLETE', reason: '' },
        ],
        resourceList: [
          { logicalId: 'AppBucket', type: 'AWS::S3::Bucket', physicalId: 'my-lab-stack-appbucket-abc123', status: 'CREATE_COMPLETE' },
          { logicalId: 'AppSecurityGroup', type: 'AWS::EC2::SecurityGroup', physicalId: 'sg-0demo1234567890', status: 'CREATE_COMPLETE' },
        ],
        outputs: [{ key: 'BucketName', value: 'my-lab-stack-appbucket-abc123', description: 'Name of the app bucket' }],
      })],
      'change-sets': [row('changeset-lab001', r, 'my-lab-stack-change-set', { status: 'CREATE_COMPLETE', changes: 2 })],
    },
    route53: {
      'hosted-zones': [row('Z1234567890ABC', '', 'example.internal', {
        type: 'Private', records: 2, status: 'available',
        recordSets: [
          { name: 'api.example.internal', type: 'A', value: '10.0.1.20', ttl: 300 },
          { name: 'www.example.internal', type: 'CNAME', value: 'api.example.internal', ttl: 60 },
        ],
      })],
      'health-checks': [row('hc-demo001', '', 'api-health-check', { protocol: 'HTTPS', status: 'Healthy' })],
    },
    sns: {
      topics: [row('topic-demo001', r, 'my-alerts-topic', { type: 'Standard', subscriptions: 1, status: 'Active', published: 0 })],
      subscriptions: [row('sub-demo001', r, 'admin@example.com', { protocol: 'Email', status: 'Confirmed' })],
    },
    sqs: {
      queues: [row('queue-demo001', r, 'orders-queue', { type: 'Standard', messages: 3, status: 'Active' })],
    },
    secretsmanager: {
      secrets: [row('secret-demo001', r, 'prod/db/password', {
        rotation: 'Disabled', lastChanged: 'Today', status: 'Active',
        secretValue: 'lab-db-password-v1', versions: 1,
      })],
    },
    acm: {
      certificates: [row('cert-demo001', r, '*.example.com', { type: 'Amazon issued', status: 'Issued', expires: '2027-03-01' })],
    },
    cloudfront: {
      distributions: [row('E1234567890ABC', '', 'web-assets-cdn', { domainName: 'd111111abcdef8.cloudfront.net', status: 'Deployed', priceClass: 'Use all edge locations' })],
    },
    eks: {
      clusters: [row('cluster-lab001', r, 'lab-eks-cluster', { version: '1.30', nodes: 3, status: 'Active' })],
      'node-groups': [row('ng-demo001', r, 'general-workers', { instanceType: 't3.medium', desired: 3, status: 'Active' })],
    },
    ecs: {
      clusters: [row('ecscluster-lab001', r, 'default', { services: 1, tasks: 2, status: 'Active' })],
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
      databases: [row('glue-db-lab001', r, 'lakehouse', { tables: 6, status: 'Active' })],
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
      alias: 'my-aws-lab',
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
      { id: 'rtb-0a1b2c3d4e5f67892', region: 'us-east-1', vpcId: 'vpc-0a1b2c3d4e5f67890', main: true, associations: ['subnet-0a1b2c3d4e5f10001', 'subnet-0a1b2c3d4e5f10002', 'subnet-0a1b2c3d4e5f10003'], routes: [{ dest: '172.31.0.0/16', target: 'local' }, { dest: '0.0.0.0/0', target: 'igw-0a1b2c3d4e5f67891' }] },
    ],
    networkAcls: [
      {
        id: 'acl-0a1b2c3d4e5f67893', region: 'us-east-1', vpcId: 'vpc-0a1b2c3d4e5f67890', default: true,
        associations: ['subnet-0a1b2c3d4e5f10001', 'subnet-0a1b2c3d4e5f10002', 'subnet-0a1b2c3d4e5f10003'],
        inbound: [
          { rule: 100, protocol: '-1', action: 'allow', cidr: '0.0.0.0/0', from: 0, to: 65535 },
          { rule: 32767, protocol: '-1', action: 'deny', cidr: '0.0.0.0/0', from: 0, to: 65535 },
        ],
        outbound: [
          { rule: 100, protocol: '-1', action: 'allow', cidr: '0.0.0.0/0', from: 0, to: 65535 },
          { rule: 32767, protocol: '-1', action: 'deny', cidr: '0.0.0.0/0', from: 0, to: 65535 },
        ],
      },
    ],
    natGateways: [],
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
      { id: 'key-0aa11lab000001', region: 'us-east-1', name: 'lab-key-pair', type: 'rsa', fingerprint: 'a1:b2:c3:d4:e5:f6:01:02:03:04:05:06:07:08:09:0a', created: '2024-01-15T09:00:00Z' },
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
        publicIp: '54.210.123.45', privateIp: '172.31.14.52', keyName: 'lab-key-pair',
        securityGroups: ['sg-0a1b2c3web00001'], iamRole: 'EC2InstanceRole', monitoring: 'disabled',
        rootDevice: '/dev/xvda', rootVolume: 'vol-0abc123def456789a', launchTime: '2024-01-15T09:00:12Z',
        statusChecks: '2/2', checks: passedChecks(), disableApiTermination: false,
        tenancy: 'default', architecture: 'x86_64',
        tags: { Name: 'web-server-01', Environment: 'lab', Project: 'fixitlab' },
      },
      {
        id: 'i-0def456abc7890123', region: 'us-east-1', name: 'db-server-01', state: 'running',
        amiId: 'ami-0557a15b87f6559cf', os: 'ubuntu-22.04', type: 't3.small', az: 'us-east-1b',
        subnetId: 'subnet-0a1b2c3d4e5f10002', vpcId: 'vpc-0a1b2c3d4e5f67890',
        publicIp: '', privateIp: '172.31.28.33', keyName: 'lab-key-pair',
        securityGroups: ['sg-0a1b2c3db000002'], iamRole: '', monitoring: 'disabled',
        rootDevice: '/dev/xvda', rootVolume: 'vol-0def456abc789012b', launchTime: '2024-01-16T10:22:00Z',
        statusChecks: '2/2', checks: passedChecks(), disableApiTermination: false,
        tenancy: 'default', architecture: 'x86_64',
        tags: { Name: 'db-server-01', Environment: 'lab' },
      },
      {
        id: 'i-0ghi789jkl0123456', region: 'us-east-1', name: 'app-server-01', state: 'stopped',
        amiId: 'ami-026ebd4cfe2c043b2', os: 'rhel-9', type: 't3.medium', az: 'us-east-1c',
        subnetId: 'subnet-0a1b2c3d4e5f10003', vpcId: 'vpc-0a1b2c3d4e5f67890',
        publicIp: '', privateIp: '172.31.42.11', keyName: 'lab-key-pair',
        securityGroups: ['sg-0a1b2c3web00001'], iamRole: '', monitoring: 'disabled',
        rootDevice: '/dev/xvda', rootVolume: 'vol-0ghi789jkl012345c', launchTime: '2024-02-10T08:00:00Z',
        statusChecks: '0/2', checks: noChecks(), disableApiTermination: false,
        tenancy: 'default', architecture: 'x86_64',
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
    cwDashboards: [
      { name: 'Production-Overview', region: 'us-east-1', widgets: 6, created: '2024-02-01T09:00:00Z' },
    ],

    // ---- EBS snapshots ----
    snapshots: [
      { id: 'snap-0demo1234567890a', region: 'us-east-1', volumeId: 'vol-0abc123def456789a', size: 8, state: 'completed', progress: '100%', description: 'web-server-01 root', started: '2024-03-01T02:00:00Z', encrypted: true },
    ],

    // ---- ELB / target groups / ASG ----
    loadBalancers: [
      { id: 'elb-0demoweb00000001', region: 'us-east-1', name: 'web-alb', type: 'application', scheme: 'internet-facing', state: 'active', dnsName: 'web-alb-1234567890.us-east-1.elb.amazonaws.com', vpcId: 'vpc-0a1b2c3d4e5f67890', targetGroups: ['tg-0demoweb00000001'], created: '2024-02-01T09:00:00Z' },
    ],
    targetGroups: [
      { id: 'tg-0demoweb00000001', region: 'us-east-1', name: 'web-targets', protocol: 'HTTP', port: 80, vpcId: 'vpc-0a1b2c3d4e5f67890', targetType: 'instance', targets: [{ id: 'i-0abc123def4567890', port: 80, health: 'healthy' }], created: '2024-02-01T09:00:00Z' },
    ],
    autoScalingGroups: [
      { id: 'asg-0demoweb00000001', region: 'us-east-1', name: 'web-asg', min: 1, max: 4, desired: 2, instanceIds: [], launchTemplate: 'web-lt', vpcId: 'vpc-0a1b2c3d4e5f67890', status: 'active', created: '2024-02-01T09:00:00Z' },
    ],

    genericResources: seedGenericResources(),

    // ---- IAM engine: who am I ----
    currentPrincipal: {
      type: 'user',
      name: 'admin-user',
      arn: `arn:aws:iam::${ACCOUNT_ID}:user/admin-user`,
      userId: 'AIDAADMIN0000000ADMIN',
      policyNames: ['AdministratorAccess'],
      policies: policiesFromNames(['AdministratorAccess']),
    },

    // ---- Console chrome (consumed by chrome UI agent) ----
    favorites: [],
    recentServices: [],
    homeWidgets: ['recently-visited', 'welcome', 'cost-and-usage', 'health', 'trusted-advisor'],
    settings: { region: 'us-east-1', theme: 'light' },

    flash: [], // {id, type, message}
    labManagedIds: [], // instance/bucket ids created during an active lab session
    // Session id of the active LabRunner session, when this console is embedded
    // in a lab (set by AwsLabOverlay on mount). Lets mutating actions (attach
    // volume, power ops) notify the cross-tech bridge in addition to the
    // normal _syncAction grading mirror. Never persisted — see partialize.
    labSessionId: null,
  }
}

let flashSeq = 1

// ---------- Lab action sync (GUI clicks -> server-side action log) ----------
// When an AWS lab session is active, every mutating console action is mirrored
// to the server-authoritative engine (aws_engine.py) so validate_aws_lab grades
// the learner's real GUI clicks — not a fresh, never-touched server world.
//
// Design: fire-and-forget, debounced, offline-safe. Actions are queued and
// flushed in order on a short debounce so a burst of edits (e.g. launch wizard)
// coalesces into a few sequential POSTs without blocking the optimistic UI. A
// failed/offline sync is swallowed (awsSimApi.syncAction never rejects) so the
// console keeps working; the next successful "Check" simply grades whatever the
// server has recorded so far.
const _labSync = {
  sessionId: null,
  queue: [],
  timer: null,
  flushing: false,
}

const SYNC_DEBOUNCE_MS = 250

function labSyncArm(sessionId) {
  _labSync.sessionId = sessionId || null
  _labSync.queue = []
  if (_labSync.timer) { clearTimeout(_labSync.timer); _labSync.timer = null }
}

function labSyncDisarm() {
  _labSync.sessionId = null
  _labSync.queue = []
  if (_labSync.timer) { clearTimeout(_labSync.timer); _labSync.timer = null }
}

async function labSyncFlush() {
  if (_labSync.flushing) return
  const sid = _labSync.sessionId
  if (!sid) { _labSync.queue = []; return }
  _labSync.flushing = true
  try {
    // Drain in FIFO order so server state advances the same way the GUI did.
    while (_labSync.queue.length && _labSync.sessionId === sid) {
      const { action, payload } = _labSync.queue.shift()
      // syncAction resolves null (never rejects) on any failure/offline.
      await awsSimApi.syncAction(sid, action, payload)
    }
  } catch { /* offline / unexpected — drop silently, UI already updated */ }
  finally { _labSync.flushing = false }
}

/** Enqueue one translated engine action; schedules a debounced flush. No-op when no lab session is armed. */
function labSyncEnqueue(action, payload) {
  if (!_labSync.sessionId || !action) return
  _labSync.queue.push({ action, payload: payload || {} })
  if (_labSync.timer) clearTimeout(_labSync.timer)
  _labSync.timer = setTimeout(() => { _labSync.timer = null; labSyncFlush() }, SYNC_DEBOUNCE_MS)
}

// ---------- Generic-resource lifecycle helpers ----------
function genericCfg(service, resource) {
  return SERVICE_CONFIGS[service]?.resources?.[resource]
}

/** Immutably map one row inside genericResources[service][resource]. */
function mapGeneric(s, service, resource, id, fn) {
  return {
    genericResources: {
      ...(s.genericResources || {}),
      [service]: {
        ...(s.genericResources?.[service] || {}),
        [resource]: (s.genericResources?.[service]?.[resource] || []).map((x) => (x.id === id ? fn(x) : x)),
      },
    },
  }
}

function removeGeneric(s, service, resource, id) {
  return {
    genericResources: {
      ...(s.genericResources || {}),
      [service]: {
        ...(s.genericResources?.[service] || {}),
        [resource]: (s.genericResources?.[service]?.[resource] || []).filter((x) => x.id !== id),
      },
    },
  }
}

/**
 * Merge a persisted (possibly old-version / partially-corrupt) blob onto the
 * fresh store. Every field is coerced to a safe default: arrays that are missing
 * or the wrong type fall back to seed arrays, object-shaped chrome fields are
 * shallow-merged onto seed, and genericResources is deep-merged per service.
 * A returning user's own resources survive; new v3 fields appear seeded.
 * Pure + defensive so the persist merge() can call it inside a try/catch.
 */
function mergePersistedAws(persisted, current) {
  const seed = seedState()
  const p = persisted && typeof persisted === 'object' && !Array.isArray(persisted) ? persisted : {}
  const merged = { ...current, ...p, flash: [] }
  merged.account = { ...seed.account, ...(p.account && typeof p.account === 'object' ? p.account : {}) }
  merged.region = (typeof p.region === 'string' && p.region) || current.region || seed.region
  merged.darkMode = typeof p.darkMode === 'boolean' ? p.darkMode : (current.darkMode ?? false)
  // Object-shaped chrome / principal fields: shallow-merge onto seed defaults.
  merged.currentPrincipal = p.currentPrincipal && typeof p.currentPrincipal === 'object'
    ? { ...seed.currentPrincipal, ...p.currentPrincipal }
    : seed.currentPrincipal
  merged.settings = { ...seed.settings, ...(p.settings && typeof p.settings === 'object' ? p.settings : {}) }
  const objectKeys = new Set(['account', 'region', 'darkMode', 'flash', 'genericResources', 'currentPrincipal', 'settings'])
  for (const key of Object.keys(seed)) {
    if (objectKeys.has(key)) continue
    if (Array.isArray(seed[key])) {
      merged[key] = Array.isArray(p[key]) ? p[key] : seed[key]
    }
  }
  // genericResources: deep-merge per service so new nested seeds appear for old
  // persisted state while user rows survive. Guard each level's type.
  if (p.genericResources && typeof p.genericResources === 'object' && !Array.isArray(p.genericResources)) {
    const g = { ...seed.genericResources }
    for (const svc of Object.keys(p.genericResources)) {
      const pv = p.genericResources[svc]
      g[svc] = { ...(seed.genericResources[svc] || {}), ...(pv && typeof pv === 'object' ? pv : {}) }
    }
    merged.genericResources = g
  } else {
    merged.genericResources = seed.genericResources
  }
  return merged
}

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

      // ---------- Lab action sync ----------
      // Arm/disarm mirroring of GUI mutations to the server-side action log for
      // grading. Called by AwsLabOverlay with the LabSession id (armed on mount,
      // disarmed on unmount). Sandbox / non-lab use passes no session and stays
      // purely local. `_syncAction` is the internal hook mutating actions call.
      armLabSync: (sessionId) => { labSyncArm(sessionId) },
      disarmLabSync: () => { labSyncDisarm() },
      isLabSyncArmed: () => Boolean(_labSync.sessionId),
      _syncAction: (action, payload) => { labSyncEnqueue(action, payload) },

      // Cross-tech bridge session id — set by AwsLabOverlay alongside armLabSync
      // so attachVolume/instanceAction can additionally notify the shared
      // AWS/Linux bridge (bridge_attach_volume / bridge_power) for labs where
      // the EC2 instance is also visible from a Linux terminal or VMware sim.
      setLabSessionId: (sessionId) => set({ labSessionId: sessionId || null }),

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
            launchTime: new Date().toISOString(), statusChecks: 'initializing', checks: initializingChecks(),
            disableApiTermination: false, tenancy: 'default',
            architecture: getInstanceType(type).arch,
            workload: ami.workload || 'linux',
            tags: { ...(name ? { Name: name } : {}), ...(tags || {}) },
            // durable transition: pending -> running
            stateTransitionAt: dueIn(EC2_TIMING.pendingToRunning),
            pendingTransition: { kind: 'ec2', to: 'running', phase: 'boot' },
          })
          set((s) => ({
            volumes: [...s.volumes, { id: rootVol, region, size: volumeSize || 8, type: volumeType || 'gp3', state: 'in-use', az, encrypted: false, attachedTo: id, device: '/dev/xvda', created: new Date().toISOString() }],
          }))
        }
        set((s) => ({ instances: [...s.instances, ...created] }))
        get()._ensureTick()
        // Mirror the launch to the server-side action log for grading.
        get()._syncAction('launch_instance', {
          name: name || '',
          instance_type: type,
          ami_id: amiId,
          count,
          subnet_id: subnetId || '',
          security_groups: securityGroups || [],
          key_name: keyName || '',
          volume_size: volumeSize || 8,
          volume_type: volumeType || 'gp3',
          monitoring: !!monitoring,
          tags: { ...(name ? { Name: name } : {}), ...(tags || {}) },
        })
        return created
      },

      instanceAction: (ids, action) => {
        const transitions = {
          start: { interim: 'pending', to: 'running', delay: EC2_TIMING.pendingToRunning, phase: 'boot' },
          stop: { interim: 'stopping', to: 'stopped', delay: EC2_TIMING.stopping },
          reboot: { interim: 'rebooting', to: 'running', delay: EC2_TIMING.rebooting, phase: 'boot' },
          terminate: { interim: 'shutting-down', to: 'terminated', delay: EC2_TIMING.shuttingDown },
        }
        const t = transitions[action]
        if (!t) return { ok: false }
        // Guard: termination protection.
        if (action === 'terminate') {
          const { instances } = get()
          const blocked = instances.filter((x) => ids.includes(x.id) && x.disableApiTermination)
          if (blocked.length) {
            const err = operationNotPermitted('TerminateInstances', `The instance '${blocked[0].id}' may not be terminated. Modify its 'disableApiTermination' instance attribute and try again.`)
            get().pushFlash('error', err.str)
            return fail(err)
          }
        }
        set((s) => ({
          instances: s.instances.map((x) => {
            if (!ids.includes(x.id)) return x
            const checks = action === 'stop' || action === 'terminate' ? noChecks() : initializingChecks()
            return {
              ...x,
              state: t.interim,
              statusChecks: action === 'stop' || action === 'terminate' ? '-' : 'initializing',
              checks,
              stateTransitionAt: dueIn(t.delay),
              pendingTransition: { kind: 'ec2', to: t.to, phase: t.phase || null },
            }
          }),
        }))
        get()._ensureTick()
        // Mirror lifecycle op to the server log. Identify by Name tag when the
        // instance has one (seed + named launches survive the client<->server id
        // gap); fall back to the raw id. The engine matches id OR name OR Name.
        const { instances: liveInstances } = get()
        const idents = ids.map((id) => {
          const inst = liveInstances.find((x) => x.id === id)
          return inst?.tags?.Name || inst?.name || id
        })
        get()._syncAction('instance_action', { op: action, instance_ids: idents })
        // Power ops (not terminate — the bridge only tracks a running/stopped
        // guest, not deletion) additionally notify the cross-tech bridge so a
        // Linux terminal / VMware sim sharing this lab session sees the guest
        // power state change without a separate manual step.
        if (get().labSessionId && ['start', 'stop', 'reboot'].includes(action)) {
          notifyAwsBridge(get().labSessionId, 'bridge_power', { op: action, instance_ids: idents })
        }
        return ok()
      },

      // Toggle EC2 termination protection.
      setDisableApiTermination: (id, value) => {
        set((s) => ({
          instances: s.instances.map((x) => (x.id === id ? { ...x, disableApiTermination: !!value } : x)),
        }))
        get()._syncAction('set_termination_protection', { instance_id: id, value: !!value })
        return ok()
      },

      // ---------- Durable lifecycle engine ----------
      // Resolve every past-due transition (EC2 + generic + LB/TG health) and
      // re-arm the single global tick. Safe to call repeatedly.
      reconcile: () => {
        const now = Date.now()
        set((s) => {
          let instances = s.instances || []
          let changed = false
          // Rescue instances left in a transient state by a pre-v3 setTimeout
          // model (no durable pendingTransition): resolve to a settled state.
          instances = instances.map((x) => {
            if (!x.pendingTransition && !x.stateTransitionAt) {
              if (x.state === 'pending' || x.state === 'rebooting') { changed = true; return { ...x, state: 'running', statusChecks: '2/2', checks: passedChecks() } }
              if (x.state === 'stopping') { changed = true; return { ...x, state: 'stopped', statusChecks: '-', checks: noChecks() } }
              if (x.state === 'shutting-down') { changed = true; return { ...x, state: 'terminated', statusChecks: '-', checks: noChecks(), publicIp: '', terminatedAt: now } }
            }
            return x
          })
          instances = instances.map((x) => {
            if (!x.pendingTransition || !x.stateTransitionAt) return x
            if (x.stateTransitionAt > now) return x
            changed = true
            const pt = x.pendingTransition
            // EC2 boot: land in running with 2-phase checks staggered.
            if (pt.to === 'running') {
              return { ...x, state: 'running', statusChecks: '1/2', checks: phase1Checks(), stateTransitionAt: dueIn(EC2_TIMING.checkPhase2), pendingTransition: { kind: 'ec2', to: 'running', phase: 'check2' } }
            }
            if (pt.to === 'stopped') {
              return { ...x, state: 'stopped', statusChecks: '-', checks: noChecks(), stateTransitionAt: null, pendingTransition: null }
            }
            if (pt.to === 'terminated') {
              return { ...x, state: 'terminated', statusChecks: '-', checks: noChecks(), publicIp: '', terminatedAt: now, stateTransitionAt: null, pendingTransition: null }
            }
            return { ...x, stateTransitionAt: null, pendingTransition: null }
          })
          // Second-phase check completion: 1/2 -> 2/2.
          instances = instances.map((x) => {
            if (x.pendingTransition?.phase === 'check2' && x.stateTransitionAt && x.stateTransitionAt <= now) {
              changed = true
              return { ...x, statusChecks: '2/2', checks: passedChecks(), stateTransitionAt: null, pendingTransition: null }
            }
            return x
          })
          // Hide long-terminated instances from lists.
          const before = instances.length
          instances = instances.filter((x) => !(x.state === 'terminated' && x.terminatedAt && now - x.terminatedAt > EC2_TIMING.terminatedLinger))
          if (instances.length !== before) changed = true

          // Generic resources: advance create walks + action interims + deletions.
          let generic = s.genericResources || {}
          let gChanged = false
          const nextGeneric = {}
          for (const [svc, resources] of Object.entries(generic)) {
            nextGeneric[svc] = {}
            for (const [res, rows] of Object.entries(resources || {})) {
              nextGeneric[svc][res] = (rows || []).flatMap((row) => {
                if (!row.pendingTransition || !row.stateTransitionAt || row.stateTransitionAt > now) return [row]
                gChanged = true
                const pt = row.pendingTransition
                if (pt.op === 'delete') return [] // remove
                if (pt.op === 'create' && Array.isArray(pt.states) && pt.step < pt.states.length - 1) {
                  const step = pt.step + 1
                  const status = pt.states[step]
                  const done = step >= pt.states.length - 1
                  const extra = svc === 'cloudformation' && res === 'stacks' && done
                    ? { resources: (row.resourceList || []).length || row.resources }
                    : {}
                  return [{ ...row, status, ...extra, stateTransitionAt: done ? null : dueIn(pt.delayMs || GENERIC_TIMING.createStep), pendingTransition: done ? null : { ...pt, step } }]
                }
                // action interim -> final
                return [{ ...row, status: pt.final ?? row.status, ...(pt.patch || {}), stateTransitionAt: null, pendingTransition: null }]
              })
            }
          }
          if (gChanged) generic = nextGeneric

          // Target-group health cycling (healthy/unhealthy flap for realism).
          let tgs = s.targetGroups || []
          let tgChanged = false
          tgs = tgs.map((tg) => {
            if (!tg.targets || !tg.targets.length) return tg
            const targets = tg.targets.map((t) => {
              if (t.health === 'initial' && Math.random() < 0.5) { tgChanged = true; return { ...t, health: 'healthy' } }
              return t
            })
            return tgChanged ? { ...tg, targets } : tg
          })

          const patch = {}
          if (changed) patch.instances = instances
          if (gChanged) patch.genericResources = generic
          if (tgChanged) patch.targetGroups = tgs
          return patch
        })
        // Keep ticking if anything is still mid-transition.
        const st = get()
        const busy = (st.instances || []).some((x) => x.pendingTransition)
          || Object.values(st.genericResources || {}).some((rs) => Object.values(rs || {}).some((rows) => (rows || []).some((r) => r.pendingTransition)))
        if (busy) get()._ensureTick()
      },

      // Arm the single global 1s tick (module-level guarded).
      _ensureTick: () => { armLifecycleTick(() => { try { get().reconcile() } catch { /* ignore */ } }) },

      setInstanceName: (id, name) => {
        const prev = get().instances.find((x) => x.id === id)
        set((s) => ({
          instances: s.instances.map((x) => (x.id === id ? { ...x, name, tags: { ...x.tags, Name: name } } : x)),
        }))
        // Mirror the rename as a tag update (identify by prior Name/id).
        get()._syncAction('set_tags', { instance_id: prev?.tags?.Name || prev?.name || id, tags: { Name: name } })
      },

      // Add/replace instance tags (used by the EC2 tag editor). Mirrors to the
      // server-side action log so the "add tag key=value" objective is gradeable.
      setInstanceTags: (id, tags) => {
        const patch = tags && typeof tags === 'object' ? tags : {}
        const prev = get().instances.find((x) => x.id === id)
        set((s) => ({
          instances: s.instances.map((x) => (x.id === id
            ? { ...x, tags: { ...x.tags, ...patch }, ...(patch.Name ? { name: patch.Name } : {}) }
            : x)),
        }))
        get()._syncAction('set_tags', { instance_id: prev?.tags?.Name || prev?.name || id, tags: patch })
        return ok()
      },

      // ---------- Key pairs ----------
      createKeyPair: ({ name, type }) => {
        const { region } = get()
        const kp = { id: newKeyPairId(), region, name, type: type || 'rsa', fingerprint: Array.from({ length: 16 }, () => Math.floor(Math.random() * 256).toString(16).padStart(2, '0')).join(':'), created: new Date().toISOString() }
        set((s) => ({ keyPairs: [...s.keyPairs, kp] }))
        get()._syncAction('create_key_pair', { name: kp.name, type: kp.type, key_pair_id: kp.id })
        return kp
      },
      deleteKeyPair: (name) => {
        set((s) => ({ keyPairs: s.keyPairs.filter((k) => k.name !== name) }))
        get()._syncAction('delete_key_pair', { name })
        return ok()
      },

      // ---------- Security groups ----------
      createSecurityGroup: ({ name, description, vpcId, inbound }) => {
        const { region, securityGroups } = get()
        if (duplicateSgNameInVpc(name, vpcId, securityGroups)) {
          const err = invalidGroupInUse('CreateSecurityGroup', `The security group '${name}' already exists for VPC '${vpcId}'`)
          get().pushFlash('error', err.str)
          return fail(err)
        }
        const sg = { id: newSgId(), region, name, description, vpcId, inbound: inbound || [], outbound: [{ id: 'sgr-o', type: 'All traffic', protocol: 'All', from: 0, to: 65535, source: '0.0.0.0/0', description: '' }] }
        set((s) => ({ securityGroups: [...s.securityGroups, sg] }))
        get()._syncAction('create_security_group', {
          name, description: description || '', vpc_id: vpcId, inbound: inbound || [],
        })
        return sg
      },
      // Guarded: SG cannot be deleted if attached to a live instance or referenced by another SG.
      deleteSecurityGroup: (id) => {
        const { securityGroups, instances } = get()
        const attached = instances.some((i) => i.state !== 'terminated' && (i.securityGroups || []).includes(id))
        if (attached) {
          const err = dependencyViolation('DeleteSecurityGroup', `resource ${id} has a dependent object`)
          get().pushFlash('error', err.str)
          return fail(err)
        }
        const referenced = securityGroups.some((sg) => sg.id !== id && [...(sg.inbound || []), ...(sg.outbound || [])].some((r) => r.source === id))
        if (referenced) {
          const err = dependencyViolation('DeleteSecurityGroup', `resource ${id} has a dependent object`)
          get().pushFlash('error', err.str)
          return fail(err)
        }
        set((s) => ({ securityGroups: s.securityGroups.filter((sg) => sg.id !== id) }))
        get()._syncAction('delete_security_group', { group_id: id })
        return ok()
      },
      // SG rule CRUD. direction = 'inbound' | 'outbound'.
      // The server engine grades ingress by (port, source), so mirror each rule
      // change as an add_sg_rule / remove_sg_rule identified by group id + port +
      // source (robust across the client<->server rule-id gap).
      addSgRule: (id, direction, rule) => {
        const dir = direction === 'outbound' ? 'outbound' : 'inbound'
        const r = { id: newSgRuleId(), ...rule }
        set((s) => ({ securityGroups: s.securityGroups.map((sg) => (sg.id === id ? { ...sg, [dir]: [...(sg[dir] || []), r] } : sg)) }))
        get()._syncAction('add_sg_rule', {
          group_id: id, direction: dir, type: r.type, protocol: r.protocol,
          from_port: r.from, to_port: r.to, source: r.source, description: r.description || '',
        })
        return r
      },
      updateSgRule: (id, direction, ruleId, patch) => {
        const dir = direction === 'outbound' ? 'outbound' : 'inbound'
        const sg = get().securityGroups.find((g) => g.id === id)
        const before = (sg?.[dir] || []).find((r) => r.id === ruleId)
        set((s) => ({ securityGroups: s.securityGroups.map((g) => (g.id === id ? { ...g, [dir]: (g[dir] || []).map((r) => (r.id === ruleId ? { ...r, ...patch } : r)) } : g)) }))
        // Mirror as remove(old) + add(new) so the server's (port, source) view tracks the edit.
        if (before) get()._syncAction('remove_sg_rule', { group_id: id, direction: dir, port: before.from, source: before.source })
        const after = { ...(before || {}), ...patch }
        get()._syncAction('add_sg_rule', {
          group_id: id, direction: dir, type: after.type, protocol: after.protocol,
          from_port: after.from, to_port: after.to, source: after.source, description: after.description || '',
        })
        return ok()
      },
      deleteSgRule: (id, direction, ruleId) => {
        const dir = direction === 'outbound' ? 'outbound' : 'inbound'
        const sg = get().securityGroups.find((g) => g.id === id)
        const target = (sg?.[dir] || []).find((r) => r.id === ruleId)
        set((s) => ({ securityGroups: s.securityGroups.map((g) => (g.id === id ? { ...g, [dir]: (g[dir] || []).filter((r) => r.id !== ruleId) } : g)) }))
        if (target) get()._syncAction('remove_sg_rule', { group_id: id, direction: dir, port: target.from, source: target.source })
        return ok()
      },
      setSgRules: (id, direction, rules) => {
        const dir = direction === 'outbound' ? 'outbound' : 'inbound'
        const sg = get().securityGroups.find((g) => g.id === id)
        const before = (sg?.[dir] || [])
        const next = (rules || [])
        set((s) => ({ securityGroups: s.securityGroups.map((g) => (g.id === id ? { ...g, [dir]: next.map((r) => ({ id: r.id || newSgRuleId(), ...r })) } : g)) }))
        // Diff by (port, source) so the bulk Save mirrors as discrete add/remove ops.
        const keyOf = (r) => `${r.from}|${r.to}|${r.source}`
        const beforeKeys = new Set(before.map(keyOf))
        const nextKeys = new Set(next.map(keyOf))
        before.filter((r) => !nextKeys.has(keyOf(r))).forEach((r) => {
          get()._syncAction('remove_sg_rule', { group_id: id, direction: dir, port: r.from, source: r.source })
        })
        next.filter((r) => !beforeKeys.has(keyOf(r))).forEach((r) => {
          get()._syncAction('add_sg_rule', {
            group_id: id, direction: dir, type: r.type, protocol: r.protocol,
            from_port: r.from, to_port: r.to, source: r.source, description: r.description || '',
          })
        })
        return ok()
      },

      // ---------- VPC ----------
      createVpc: ({ name, cidr, tenancy }) => {
        const { region, vpcs } = get()
        if (!isValidCidr(cidr)) {
          const err = invalidParameterValue('CreateVpc', `Value (${cidr}) for parameter cidrBlock is invalid. This is not a valid CIDR block.`)
          get().pushFlash('error', err.str)
          return fail(err)
        }
        if (vpcs.some((v) => v.region === region && cidrsOverlap(v.cidr, cidr))) {
          const err = invalidParameterValue('CreateVpc', `The CIDR '${cidr}' conflicts with another VPC.`)
          get().pushFlash('error', err.str)
          return fail(err)
        }
        const vpc = { id: newVpcId(), region, name: name || '', cidr, state: 'available', isDefault: false, dnsHostnames: false, dnsSupport: true, tenancy: tenancy || 'default' }
        set((s) => ({ vpcs: [...s.vpcs, vpc] }))
        get()._syncAction('create_vpc', { vpc_id: vpc.id, name: vpc.name, cidr: vpc.cidr, tenancy: vpc.tenancy })
        return vpc
      },
      deleteVpc: (id) => {
        const { subnets, internetGateways, securityGroups, instances } = get()
        const hasInstances = instances.some((i) => i.state !== 'terminated' && i.vpcId === id)
        const hasSubnets = subnets.some((sn) => sn.vpcId === id)
        const hasIgw = internetGateways.some((g) => g.vpcId === id)
        const hasSg = securityGroups.some((sg) => sg.vpcId === id && sg.name !== 'default')
        if (hasInstances || hasSubnets || hasIgw || hasSg) {
          const err = dependencyViolation('DeleteVpc', `The vpc '${id}' has dependencies and cannot be deleted.`)
          get().pushFlash('error', err.str)
          return fail(err)
        }
        set((s) => ({ vpcs: s.vpcs.filter((v) => v.id !== id), securityGroups: s.securityGroups.filter((sg) => sg.vpcId !== id) }))
        get()._syncAction('delete_vpc', { vpc_id: id })
        return ok()
      },

      // ---------- Subnets ----------
      createSubnet: ({ vpcId, cidr, az, mapPublicIp }) => {
        const { region, vpcs, subnets } = get()
        const vpc = vpcs.find((v) => v.id === vpcId)
        if (!vpc) {
          const err = invalidParameterValue('CreateSubnet', `The vpc ID '${vpcId}' does not exist`)
          get().pushFlash('error', err.str)
          return fail(err)
        }
        if (!isValidCidr(cidr) || !cidrWithinVpc(cidr, vpc.cidr)) {
          const err = invalidParameterValue('CreateSubnet', `The CIDR '${cidr}' is invalid or is not within the CIDR range of VPC '${vpcId}' (${vpc.cidr}).`)
          get().pushFlash('error', err.str)
          return fail(err)
        }
        if (subnets.some((sn) => sn.vpcId === vpcId && cidrsOverlap(sn.cidr, cidr))) {
          const err = invalidParameterValue('CreateSubnet', `The CIDR '${cidr}' conflicts with another subnet`)
          get().pushFlash('error', err.str)
          return fail(err)
        }
        const subnet = { id: newSubnetId(), region, vpcId, cidr, az: az || `${region}a`, availableIps: 4091, mapPublicIp: !!mapPublicIp, isDefault: false }
        set((s) => ({ subnets: [...s.subnets, subnet] }))
        get()._syncAction('create_subnet', { subnet_id: subnet.id, vpc_id: vpcId, cidr, az: subnet.az, map_public_ip: !!mapPublicIp })
        return subnet
      },
      deleteSubnet: (id) => {
        const { instances } = get()
        if (instances.some((i) => i.state !== 'terminated' && i.subnetId === id)) {
          const err = dependencyViolation('DeleteSubnet', `The subnet '${id}' has dependencies and cannot be deleted.`)
          get().pushFlash('error', err.str)
          return fail(err)
        }
        set((s) => ({ subnets: s.subnets.filter((sn) => sn.id !== id) }))
        get()._syncAction('delete_subnet', { subnet_id: id })
        return ok()
      },

      // ---------- Internet gateways ----------
      createInternetGateway: ({ name } = {}) => {
        const { region } = get()
        const igw = { id: newIgwId(), region, vpcId: null, state: 'detached', name: name || '' }
        set((s) => ({ internetGateways: [...s.internetGateways, igw] }))
        get()._syncAction('create_internet_gateway', { igw_id: igw.id, name: igw.name })
        return igw
      },
      attachInternetGateway: (id, vpcId) => {
        const { internetGateways } = get()
        if (internetGateways.some((g) => g.vpcId === vpcId && g.id !== id)) {
          const err = dependencyViolation('AttachInternetGateway', `resource ${vpcId} already has an internet gateway attached`)
          get().pushFlash('error', err.str)
          return fail(err)
        }
        set((s) => ({ internetGateways: s.internetGateways.map((g) => (g.id === id ? { ...g, vpcId, state: 'attached' } : g)) }))
        get()._syncAction('attach_internet_gateway', { igw_id: id, vpc_id: vpcId })
        return ok()
      },
      detachInternetGateway: (id) => {
        set((s) => ({ internetGateways: s.internetGateways.map((g) => (g.id === id ? { ...g, vpcId: null, state: 'detached' } : g)) }))
        get()._syncAction('detach_internet_gateway', { igw_id: id })
        return ok()
      },
      deleteInternetGateway: (id) => {
        const { internetGateways } = get()
        const g = internetGateways.find((x) => x.id === id)
        if (g && g.state === 'attached') {
          const err = dependencyViolation('DeleteInternetGateway', `The internetGateway '${id}' has dependencies and cannot be deleted. Detach it first.`)
          get().pushFlash('error', err.str)
          return fail(err)
        }
        set((s) => ({ internetGateways: s.internetGateways.filter((x) => x.id !== id) }))
        get()._syncAction('delete_internet_gateway', { igw_id: id })
        return ok()
      },

      // ---------- Route tables ----------
      createRouteTable: ({ vpcId } = {}) => {
        const { region, vpcs } = get()
        const vpc = vpcs.find((v) => v.id === vpcId) || vpcs[0]
        if (!vpc) return fail(invalidParameterValue('CreateRouteTable', 'VPC not found'))
        const rtb = {
          id: newRtbId(), region, vpcId: vpc.id, main: false, associations: [],
          routes: [{ dest: vpc.cidr, target: 'local' }],
        }
        set((s) => ({ routeTables: [...(s.routeTables || []), rtb] }))
        get()._syncAction('create_route_table', { rtb_id: rtb.id, vpc_id: vpc.id })
        return rtb
      },
      createRoute: (rtbId, { dest, target } = {}) => {
        const { routeTables } = get()
        const rtb = routeTables.find((r) => r.id === rtbId)
        if (!rtb) return fail(invalidParameterValue('CreateRoute', `The routeTable ID '${rtbId}' does not exist`))
        const route = { dest: dest || '0.0.0.0/0', target: target || 'igw-local' }
        set((s) => ({
          routeTables: s.routeTables.map((r) => (
            r.id === rtbId
              ? { ...r, routes: [...(r.routes || []).filter((x) => x.dest !== route.dest), route] }
              : r
          )),
        }))
        get()._syncAction('create_route', { rtb_id: rtbId, dest: route.dest, target: route.target })
        return ok()
      },
      associateRouteTable: (rtbId, subnetId) => {
        const { routeTables, subnets } = get()
        const rtb = routeTables.find((r) => r.id === rtbId)
        const subnet = subnets.find((s) => s.id === subnetId)
        if (!rtb) return fail(invalidParameterValue('AssociateRouteTable', `The routeTable ID '${rtbId}' does not exist`))
        if (!subnet) return fail(invalidParameterValue('AssociateRouteTable', `The subnet ID '${subnetId}' does not exist`))
        set((s) => ({
          routeTables: s.routeTables.map((r) => {
            const assocs = (r.associations || []).filter((a) => a !== subnetId)
            if (r.id === rtbId && !assocs.includes(subnetId)) assocs.push(subnetId)
            return { ...r, associations: assocs }
          }),
        }))
        get()._syncAction('associate_route_table', { rtb_id: rtbId, subnet_id: subnetId })
        return ok()
      },
      deleteRouteTable: (id) => {
        const { routeTables } = get()
        const rtb = routeTables.find((r) => r.id === id)
        if (rtb?.main) {
          const err = dependencyViolation('DeleteRouteTable', `The main route table '${id}' cannot be deleted.`)
          get().pushFlash('error', err.str)
          return fail(err)
        }
        set((s) => ({ routeTables: (s.routeTables || []).filter((r) => r.id !== id) }))
        get()._syncAction('delete_route_table', { rtb_id: id })
        return ok()
      },

      createNetworkAcl: ({ vpcId } = {}) => {
        const { region, vpcs } = get()
        const vpc = vpcs.find((v) => v.id === vpcId) || vpcs[0]
        if (!vpc) return fail(invalidParameterValue('CreateNetworkAcl', 'VPC not found'))
        const acl = {
          id: newAclId(), region, vpcId: vpc.id, default: false, associations: [],
          inbound: [{ rule: 32767, protocol: '-1', action: 'deny', cidr: '0.0.0.0/0', from: 0, to: 65535 }],
          outbound: [{ rule: 32767, protocol: '-1', action: 'deny', cidr: '0.0.0.0/0', from: 0, to: 65535 }],
        }
        set((s) => ({ networkAcls: [...(s.networkAcls || []), acl] }))
        get()._syncAction('create_network_acl', { acl_id: acl.id, vpc_id: vpc.id })
        return acl
      },
      createNaclEntry: (aclId, { rule = 100, protocol = '-1', action = 'allow', cidr = '0.0.0.0/0', from = 0, to = 65535, egress = false } = {}) => {
        const { networkAcls } = get()
        const acl = (networkAcls || []).find((a) => a.id === aclId)
        if (!acl) return fail(invalidParameterValue('CreateNetworkAclEntry', `The networkAcl ID '${aclId}' does not exist`))
        const dir = egress ? 'outbound' : 'inbound'
        const row = { rule, protocol, action, cidr, from, to }
        set((s) => ({
          networkAcls: s.networkAcls.map((a) => {
            if (a.id !== aclId) return a
            const rules = [...(a[dir] || []).filter((r) => r.rule !== rule), row].sort((x, y) => x.rule - y.rule)
            return { ...a, [dir]: rules }
          }),
        }))
        get()._syncAction('create_nacl_entry', { acl_id: aclId, rule, protocol, action, cidr, from, to, egress })
        return ok()
      },
      replaceNaclAssociation: (aclId, subnetId) => {
        const { networkAcls, subnets } = get()
        if (!(networkAcls || []).find((a) => a.id === aclId)) {
          return fail(invalidParameterValue('ReplaceNetworkAclAssociation', `The networkAcl ID '${aclId}' does not exist`))
        }
        if (!subnets.find((s) => s.id === subnetId)) {
          return fail(invalidParameterValue('ReplaceNetworkAclAssociation', `The subnet ID '${subnetId}' does not exist`))
        }
        set((s) => ({
          networkAcls: s.networkAcls.map((a) => {
            const assocs = (a.associations || []).filter((x) => x !== subnetId)
            if (a.id === aclId && !assocs.includes(subnetId)) assocs.push(subnetId)
            return { ...a, associations: assocs }
          }),
        }))
        get()._syncAction('replace_nacl_association', { acl_id: aclId, subnet_id: subnetId })
        return ok()
      },
      deleteNetworkAcl: (id) => {
        const { networkAcls } = get()
        const acl = (networkAcls || []).find((a) => a.id === id)
        if (acl?.default) {
          const err = dependencyViolation('DeleteNetworkAcl', `The default network ACL '${id}' cannot be deleted.`)
          get().pushFlash('error', err.str)
          return fail(err)
        }
        if (acl?.associations?.length) {
          const err = dependencyViolation('DeleteNetworkAcl', `Network ACL '${id}' has subnet associations`)
          get().pushFlash('error', err.str)
          return fail(err)
        }
        set((s) => ({ networkAcls: (s.networkAcls || []).filter((a) => a.id !== id) }))
        get()._syncAction('delete_network_acl', { acl_id: id })
        return ok()
      },

      createNatGateway: ({ subnetId, allocationId } = {}) => {
        const { region, subnets, elasticIps } = get()
        const subnet = subnets.find((s) => s.id === subnetId) || subnets[0]
        if (!subnet) return fail(invalidParameterValue('CreateNatGateway', 'Subnet not found'))
        let eip = allocationId ? elasticIps.find((e) => e.allocationId === allocationId) : null
        if (!eip) {
          eip = {
            allocationId: newEipAllocId(), region, publicIp: newPublicIp(),
            associationId: null, instanceId: null, domain: 'vpc',
          }
          set((s) => ({ elasticIps: [...(s.elasticIps || []), eip] }))
          get()._syncAction('allocate_eip', { allocation_id: eip.allocationId, public_ip: eip.publicIp })
        }
        const nat = {
          id: newNatId(), region, subnetId: subnet.id, vpcId: subnet.vpcId,
          allocationId: eip.allocationId, publicIp: eip.publicIp, state: 'available',
        }
        set((s) => ({ natGateways: [...(s.natGateways || []), nat] }))
        get()._syncAction('create_nat_gateway', {
          nat_id: nat.id, subnet_id: subnet.id, allocation_id: eip.allocationId, public_ip: eip.publicIp,
        })
        return nat
      },
      deleteNatGateway: (id) => {
        set((s) => ({ natGateways: (s.natGateways || []).filter((n) => n.id !== id) }))
        get()._syncAction('delete_nat_gateway', { nat_id: id })
        return ok()
      },

      // ---------- AMIs ----------
      createImage: ({ instanceId, name, description } = {}) => {
        const { region, instances } = get()
        const inst = instances.find((i) => i.id === instanceId)
        if (!inst) return fail(invalidParameterValue('CreateImage', `The instance ID '${instanceId}' does not exist`))
        const ami = {
          id: newAmiId(),
          region,
          name: name || `${inst.name || inst.id}-ami`,
          os: inst.os || 'amazon-linux-2023',
          platform: inst.platform || 'Linux/UNIX',
          arch: 'x86_64',
          user: 'ec2-user',
          desc: description || `Created from ${inst.id}`,
          owner: ACCOUNT_ID,
          created: new Date().toISOString(),
          visibility: 'private',
        }
        set((s) => ({ amis: [...(s.amis || []), ami] }))
        get()._syncAction('create_image', {
          instance_id: instanceId, ami_id: ami.id, name: ami.name, description: ami.desc,
        })
        return ami
      },
      deregisterImage: (id) => {
        set((s) => ({ amis: (s.amis || []).filter((a) => a.id !== id) }))
        get()._syncAction('deregister_image', { ami_id: id })
        return ok()
      },

      // ---------- EBS volumes / snapshots ----------
      attachVolume: (volId, instanceId, device) => {
        const { volumes, instances } = get()
        const vol = volumes.find((v) => v.id === volId)
        const inst = instances.find((i) => i.id === instanceId)
        if (!vol) return fail(invalidParameterValue('AttachVolume', `The volume '${volId}' does not exist.`))
        if (!inst) return fail(invalidParameterValue('AttachVolume', `The instance ID '${instanceId}' does not exist`))
        if (vol.state === 'in-use') {
          const err = invalidParameterValue('AttachVolume', `Volume '${volId}' is already attached to an instance`)
          get().pushFlash('error', err.str)
          return fail(err)
        }
        const finalDevice = device || '/dev/sdf'
        set((s) => ({ volumes: s.volumes.map((v) => (v.id === volId ? { ...v, state: 'in-use', attachedTo: instanceId, device: finalDevice } : v)) }))
        get()._syncAction('attach_volume', {
          volume_id: volId, instance_id: instanceId, device: finalDevice, size_gb: vol.size,
        })
        if (get().labSessionId) {
          notifyAwsBridge(get().labSessionId, 'bridge_attach_volume', {
            volume_id: volId, instance_id: instanceId, device: finalDevice, size_gb: vol.size,
          })
        }
        return ok()
      },
      detachVolume: (volId) => {
        const { volumes, instances } = get()
        const vol = volumes.find((v) => v.id === volId)
        if (vol && instances.some((i) => i.rootVolume === volId && i.state !== 'terminated')) {
          const err = operationNotPermitted('DetachVolume', `'${volId}' is the root device and cannot be detached while the instance is running`)
          get().pushFlash('error', err.str)
          return fail(err)
        }
        const device = vol?.device || null
        const instanceId = vol?.attachedTo || null
        set((s) => ({ volumes: s.volumes.map((v) => (v.id === volId ? { ...v, state: 'available', attachedTo: null, device: null } : v)) }))
        get()._syncAction('detach_volume', { volume_id: volId, instance_id: instanceId, device })
        if (get().labSessionId) {
          notifyAwsBridge(get().labSessionId, 'bridge_detach_volume', {
            volume_id: volId, instance_id: instanceId, device,
          })
        }
        return ok()
      },
      createSnapshot: (volId, description) => {
        const { region, volumes } = get()
        const vol = volumes.find((v) => v.id === volId)
        if (!vol) return fail(invalidParameterValue('CreateSnapshot', `The volume '${volId}' does not exist.`))
        const snap = { id: newSnapshotId(), region, volumeId: volId, size: vol.size, state: 'completed', progress: '100%', description: description || '', started: new Date().toISOString(), encrypted: !!vol.encrypted }
        set((s) => ({ snapshots: [...(s.snapshots || []), snap] }))
        get()._syncAction('create_snapshot', { volume_id: volId, snapshot_id: snap.id, description: description || '' })
        return snap
      },
      deleteSnapshot: (id) => {
        set((s) => ({ snapshots: (s.snapshots || []).filter((x) => x.id !== id) }))
        get()._syncAction('delete_snapshot', { snapshot_id: id })
        return ok()
      },
      createVolume: ({ size, type, az, encrypted } = {}) => {
        const { region } = get()
        const vol = { id: newVolumeId(), region, size: size || 8, type: type || 'gp3', state: 'available', az: az || `${region}a`, encrypted: !!encrypted, attachedTo: null, device: null, created: new Date().toISOString() }
        set((s) => ({ volumes: [...s.volumes, vol] }))
        get()._syncAction('create_volume', {
          volume_id: vol.id, size_gb: vol.size, volume_type: vol.type, az: vol.az, encrypted: !!encrypted,
        })
        return vol
      },
      deleteVolume: (id) => {
        const { volumes } = get()
        const vol = volumes.find((v) => v.id === id)
        if (vol && vol.state === 'in-use') {
          const err = dependencyViolation('DeleteVolume', `Volume '${id}' is currently attached and cannot be deleted.`)
          get().pushFlash('error', err.str)
          return fail(err)
        }
        set((s) => ({ volumes: s.volumes.filter((v) => v.id !== id) }))
        get()._syncAction('delete_volume', { volume_id: id })
        return ok()
      },

      // ---------- Elastic IPs ----------
      allocateEip: () => {
        const { region } = get()
        const eip = { allocationId: newEipAllocId(), region, publicIp: newPublicIp(), associationId: null, instanceId: null, domain: 'vpc' }
        set((s) => ({ elasticIps: [...s.elasticIps, eip] }))
        get()._syncAction('allocate_eip', { allocation_id: eip.allocationId, public_ip: eip.publicIp })
        return eip
      },
      associateEip: (allocationId, instanceId) => {
        const { elasticIps, instances } = get()
        const eip = elasticIps.find((e) => e.allocationId === allocationId)
        const inst = instances.find((i) => i.id === instanceId)
        if (!eip) return fail(invalidParameterValue('AssociateAddress', `The allocation ID '${allocationId}' does not exist`))
        if (!inst) return fail(invalidParameterValue('AssociateAddress', `The instance ID '${instanceId}' does not exist`))
        const associationId = newEipAssocId()
        set((s) => ({
          elasticIps: s.elasticIps.map((e) => (e.allocationId === allocationId ? { ...e, associationId, instanceId } : e)),
          instances: s.instances.map((i) => (i.id === instanceId ? { ...i, publicIp: eip.publicIp } : i)),
        }))
        get()._syncAction('associate_eip', { allocation_id: allocationId, instance_id: instanceId, association_id: associationId })
        return ok()
      },
      disassociateEip: (allocationId) => {
        const { elasticIps } = get()
        const eip = elasticIps.find((e) => e.allocationId === allocationId)
        set((s) => ({
          elasticIps: s.elasticIps.map((e) => (e.allocationId === allocationId ? { ...e, associationId: null, instanceId: null } : e)),
          instances: eip?.instanceId ? s.instances.map((i) => (i.id === eip.instanceId ? { ...i, publicIp: '' } : i)) : s.instances,
        }))
        get()._syncAction('disassociate_eip', { allocation_id: allocationId, instance_id: eip?.instanceId })
        return ok()
      },
      releaseEip: (allocationId) => {
        const { elasticIps } = get()
        const eip = elasticIps.find((e) => e.allocationId === allocationId)
        if (eip && eip.associationId) {
          const err = invalidParameterValue('ReleaseAddress', `The address with allocation id '${allocationId}' is currently associated and cannot be released. Disassociate it first.`)
          get().pushFlash('error', err.str)
          return fail(err)
        }
        set((s) => ({ elasticIps: s.elasticIps.filter((e) => e.allocationId !== allocationId) }))
        get()._syncAction('release_eip', { allocation_id: allocationId })
        return ok()
      },

      // ---------- ELB / target groups / auto scaling ----------
      createLoadBalancer: ({ name, type, scheme, vpcId } = {}) => {
        const { region } = get()
        const lb = { id: `elb-0${Math.random().toString(16).slice(2, 18).padEnd(16, '0')}`, region, name: name || 'my-lb', type: type || 'application', scheme: scheme || 'internet-facing', state: 'active', dnsName: `${name || 'my-lb'}-${Math.floor(Math.random() * 1e9)}.${region}.elb.amazonaws.com`, vpcId: vpcId || get().vpcs[0]?.id, targetGroups: [], created: new Date().toISOString() }
        set((s) => ({ loadBalancers: [...(s.loadBalancers || []), lb] }))
        get()._syncAction('create_load_balancer', { name: lb.name, type: lb.type, scheme: lb.scheme, vpcId: lb.vpcId })
        return lb
      },
      deleteLoadBalancer: (id) => {
        set((s) => ({ loadBalancers: (s.loadBalancers || []).filter((x) => x.id !== id) }))
        get()._syncAction('delete_load_balancer', { id })
        return ok()
      },
      createTargetGroup: ({ name, protocol, port, vpcId, targetType } = {}) => {
        const { region } = get()
        const tg = { id: `tg-0${Math.random().toString(16).slice(2, 18).padEnd(16, '0')}`, region, name: name || 'my-targets', protocol: protocol || 'HTTP', port: port || 80, vpcId: vpcId || get().vpcs[0]?.id, targetType: targetType || 'instance', targets: [], created: new Date().toISOString() }
        set((s) => ({ targetGroups: [...(s.targetGroups || []), tg] }))
        get()._syncAction('create_target_group', {
          id: tg.id, name: tg.name, protocol: tg.protocol, port: tg.port, vpcId: tg.vpcId, targetType: tg.targetType,
        })
        return tg
      },
      deleteTargetGroup: (id) => {
        set((s) => ({ targetGroups: (s.targetGroups || []).filter((x) => x.id !== id) }))
        get()._syncAction('delete_target_group', { id })
        return ok()
      },
      registerTarget: (tgId, instanceId, port) => {
        set((s) => ({ targetGroups: (s.targetGroups || []).map((tg) => (tg.id === tgId ? { ...tg, targets: [...(tg.targets || []).filter((t) => t.id !== instanceId), { id: instanceId, port: port || tg.port, health: 'initial' }] } : tg)) }))
        get()._ensureTick()
        get()._syncAction('register_target', { target_group_id: tgId, instance_id: instanceId, port: port || 80 })
        return ok()
      },
      deregisterTarget: (tgId, instanceId) => {
        set((s) => ({ targetGroups: (s.targetGroups || []).map((tg) => (tg.id === tgId ? { ...tg, targets: (tg.targets || []).filter((t) => t.id !== instanceId) } : tg)) }))
        get()._syncAction('deregister_target', { target_group_id: tgId, instance_id: instanceId })
        return ok()
      },
      createAutoScalingGroup: ({ name, min, max, desired, launchTemplate, subnetId } = {}) => {
        const { region } = get()
        const subnet = get().subnets.find((sn) => sn.id === subnetId) || get().subnets.find((sn) => sn.region === region)
        const n = desired || min || 1
        const instanceIds = []
        for (let i = 0; i < n; i += 1) {
          const created = get().launchInstances({ name: `${name || 'asg'}-instance`, amiId: 'ami-0c02fb55956c7d316', type: 't3.micro', count: 1, keyName: '', subnetId: subnet?.id, securityGroups: [], monitoring: false, tags: { 'aws:autoscaling:groupName': name || 'asg' } })
          if (created && created[0]) instanceIds.push(created[0].id)
        }
        const asg = { id: `asg-0${Math.random().toString(16).slice(2, 18).padEnd(16, '0')}`, region, name: name || 'my-asg', min: min ?? 1, max: max ?? 4, desired: n, instanceIds, launchTemplate: launchTemplate || 'default-lt', vpcId: subnet?.vpcId, status: 'active', created: new Date().toISOString() }
        set((s) => ({ autoScalingGroups: [...(s.autoScalingGroups || []), asg] }))
        get()._syncAction('create_asg', {
          name: asg.name, min: asg.min, max: asg.max, desired: asg.desired,
          launchTemplate: asg.launchTemplate, vpcId: asg.vpcId,
        })
        return asg
      },
      deleteAutoScalingGroup: (id) => {
        const { autoScalingGroups } = get()
        const asg = autoScalingGroups.find((a) => a.id === id)
        if (asg && asg.instanceIds?.length) get().instanceAction(asg.instanceIds, 'terminate')
        set((s) => ({ autoScalingGroups: (s.autoScalingGroups || []).filter((a) => a.id !== id) }))
        get()._syncAction('delete_asg', { id, name: asg?.name })
        return ok()
      },
      scaleAutoScalingGroup: (id, { desired, min, max } = {}) => {
        const asg = (get().autoScalingGroups || []).find((a) => a.id === id)
        if (!asg) return fail(resourceNotFound('UpdateAutoScalingGroup', 'Auto Scaling group not found.'))
        const nextMin = min != null ? Number(min) : asg.min
        const nextMax = max != null ? Number(max) : asg.max
        let nextDesired = desired != null ? Number(desired) : asg.desired
        nextDesired = Math.max(nextMin, Math.min(nextMax, nextDesired))
        const current = (asg.instanceIds || []).length
        if (nextDesired > current) {
          for (let i = current; i < nextDesired; i += 1) {
            const created = get().launchInstances({
              name: `${asg.name}-instance`, amiId: 'ami-0c02fb55956c7d316', type: 't3.micro', count: 1,
              keyName: '', subnetId: '', securityGroups: [], monitoring: false,
              tags: { 'aws:autoscaling:groupName': asg.name },
            })
            if (created?.[0]) {
              set((s) => ({
                autoScalingGroups: (s.autoScalingGroups || []).map((a) => (
                  a.id === id ? { ...a, instanceIds: [...(a.instanceIds || []), created[0].id] } : a
                )),
              }))
            }
          }
        } else if (nextDesired < current) {
          const toTerminate = (asg.instanceIds || []).slice(nextDesired)
          if (toTerminate.length) get().instanceAction(toTerminate, 'terminate')
          set((s) => ({
            autoScalingGroups: (s.autoScalingGroups || []).map((a) => (
              a.id === id ? { ...a, instanceIds: (a.instanceIds || []).slice(0, nextDesired) } : a
            )),
          }))
        }
        set((s) => ({
          autoScalingGroups: (s.autoScalingGroups || []).map((a) => (
            a.id === id ? { ...a, desired: nextDesired, min: nextMin, max: nextMax } : a
          )),
        }))
        get()._syncAction('scale_asg', { id: asg.id, name: asg.name, desired: nextDesired, min: nextMin, max: nextMax })
        return ok({ desired: nextDesired, min: nextMin, max: nextMax })
      },

      // ---------- S3 ----------
      createBucket: ({ name, region, versioning, encryption, blockPublic }) => {
        if (!isValidBucketName(name)) {
          const err = invalidParameterValue('CreateBucket', `The specified bucket is not valid. Bucket name '${name}' does not follow Amazon S3 naming rules.`)
          get().pushFlash('error', err.str)
          return fail(err)
        }
        if (get().s3Buckets.some((b) => b.name === name)) {
          const err = { code: 'BucketAlreadyExists', str: `An error occurred (BucketAlreadyExists) when calling the CreateBucket operation: The requested bucket name is not available.` }
          get().pushFlash('error', err.str)
          return fail(err)
        }
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
        get()._syncAction('create_bucket', {
          name, region: bucket.region, versioning: !!versioning,
          block_public: blockPublic !== false, encryption: encryption || 'SSE-S3',
        })
        return bucket
      },
      deleteBucket: (name) => {
        const { s3Buckets } = get()
        const bucket = s3Buckets.find((b) => b.name === name)
        if (bucket && (bucket.objects || []).length > 0) {
          const err = bucketNotEmpty('DeleteBucket', 'The bucket you tried to delete is not empty')
          get().pushFlash('error', err.str)
          return fail(err)
        }
        set((s) => ({ s3Buckets: s.s3Buckets.filter((b) => b.name !== name) }))
        get()._syncAction('delete_bucket', { name })
        return ok()
      },
      updateBucket: (name, patch) => {
        set((s) => ({ s3Buckets: s.s3Buckets.map((b) => (b.name === name ? { ...b, ...patch } : b)) }))
        // Mirror the encryption / public-access / versioning toggles the grader reads.
        get()._syncAction('update_bucket', { name, patch: patch || {} })
        return ok()
      },
      putObject: (bucketName, key, size) => {
        set((s) => ({
          s3Buckets: s.s3Buckets.map((b) => (b.name === bucketName ? { ...b, objects: [...b.objects.filter((o) => o.key !== key), { key, size: size || 0, modified: new Date().toISOString(), storageClass: 'STANDARD', etag: `"${Math.random().toString(16).slice(2, 34).padEnd(32, '0')}"` }] } : b)),
        }))
        get()._syncAction('put_object', { bucket: bucketName, key, size: size || 0 })
        return ok()
      },
      deleteObject: (bucketName, key) => {
        set((s) => ({
          s3Buckets: s.s3Buckets.map((b) => (b.name === bucketName ? { ...b, objects: b.objects.filter((o) => o.key !== key) } : b)),
        }))
        get()._syncAction('delete_object', { bucket: bucketName, key })
        return ok()
      },

      // ---------- IAM ----------
      createIamUser: ({ name, consoleAccess, policies }) => {
        const user = { id: newIamUserId(), name, created: new Date().toISOString(), consoleAccess: !!consoleAccess, groups: [], policies: policies || [], accessKeys: [] }
        set((s) => ({ iamUsers: [...s.iamUsers, user] }))
        get()._syncAction('create_iam_user', { name, console_access: !!consoleAccess, policies: policies || [] })
        return user
      },
      deleteIamUser: (name) => {
        set((s) => ({ iamUsers: s.iamUsers.filter((u) => u.name !== name) }))
        get()._syncAction('delete_iam_user', { name })
        return ok()
      },
      createAccessKey: (userName) => {
        const key = { id: newAccessKeyId(), secret: newSecretAccessKey(), created: new Date().toISOString(), status: 'Active', lastUsed: 'N/A' }
        set((s) => ({ iamUsers: s.iamUsers.map((u) => (u.name === userName ? { ...u, accessKeys: [...u.accessKeys, { id: key.id, created: key.created, status: 'Active', lastUsed: 'N/A' }] } : u)) }))
        get()._syncAction('create_access_key', { name: userName, access_key_id: key.id })
        return key
      },
      createIamRole: ({ name, trustedEntity, policies }) => {
        const role = { id: newIamRoleId(), name, created: new Date().toISOString(), trustedEntity, policies: policies || [] }
        set((s) => ({ iamRoles: [...s.iamRoles, role] }))
        get()._syncAction('create_iam_role', { name, trusted_entity: trustedEntity, policies: policies || [] })
        return role
      },
      createIamPolicy: ({ name, description, document }) => {
        const text = typeof document === 'string' ? document : JSON.stringify(document || {})
        const check = isValidPolicyJson(text)
        if (!check.ok) {
          const err = malformedPolicyDocument('CreatePolicy', check.error)
          get().pushFlash('error', err.str)
          return fail(err)
        }
        const doc = typeof document === 'string' ? JSON.parse(document) : document
        const policy = { name, type: 'Customer managed', attached: 0, created: new Date().toISOString(), description, document: doc }
        set((s) => ({ iamPolicies: [...s.iamPolicies, policy] }))
        get()._syncAction('create_iam_policy', { name, description, document: doc })
        return policy
      },
      updateIamPolicy: (name, patch) => {
        set((s) => ({
          iamPolicies: s.iamPolicies.map((p) => (p.name === name ? { ...p, ...patch } : p)),
        }))
        get()._syncAction('update_iam_policy', { name, patch: patch || {} })
        return ok()
      },
      deleteIamPolicy: (name) => {
        set((s) => ({ iamPolicies: s.iamPolicies.filter((p) => p.name !== name) }))
        get()._syncAction('delete_iam_policy', { name })
        return ok()
      },

      // ---------- Generic services ----------
      createGenericResource: (service, resource, payload) => {
        const { region } = get()
        const cfg = genericCfg(service, resource)
        const draft = { ...(cfg?.defaults || {}), ...(payload || {}) }
        // Optional cfg.validate(name, draft, rows).
        if (cfg?.validate) {
          const rows = get().genericResources?.[service]?.[resource] || []
          const errMsg = cfg.validate(draft.name, draft, rows)
          if (errMsg) {
            const err = invalidParameterValue(`Create${resource}`, errMsg)
            get().pushFlash('error', err.str)
            return fail(err)
          }
        }
        // Optional cfg.derive(name, draft) -> patch.
        const derived = cfg?.derive ? cfg.derive(draft.name, draft) : {}
        const lc = cfg?.lifecycle
        const createStates = lc?.createStates
        const created = {
          id: newGenericId(service, resource),
          region,
          created: new Date().toISOString(),
          tags: { Environment: 'lab', Project: 'fixitlab' },
          status: createStates ? createStates[0] : (draft.status || 'Active'),
          ...draft,
          ...derived,
        }
        // Schedule the create walk to the final state via the durable tick.
        if (createStates && createStates.length > 1) {
          created.status = createStates[0]
          created.stateTransitionAt = dueIn(lc.createDelayMs || GENERIC_TIMING.createStep)
          created.pendingTransition = { op: 'create', states: createStates, step: 0, delayMs: lc.createDelayMs || GENERIC_TIMING.createStep }
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
        // Mirror to lab server so scenario grading can observe creates.
        const syncPayload = {
          service,
          resource,
          name: created.name,
          status: created.status,
          ...Object.fromEntries(
            Object.entries(created).filter(([k]) => !['id', 'region', 'created', 'tags', 'pendingTransition', 'stateTransitionAt', 'name', 'status'].includes(k)),
          ),
        }
        let syncAction = 'create_generic_resource'
        if (service === 'rds' && resource === 'databases') syncAction = 'create_rds'
        else if (service === 'dynamodb' && resource === 'tables') syncAction = 'create_dynamodb_table'
        else if (service === 'eks' && resource === 'clusters') syncAction = 'create_eks_cluster'
        else if (service === 'ecs' && resource === 'services') syncAction = 'create_ecs_service'
        else if (service === 'lambda' && resource === 'functions') syncAction = 'create_lambda'
        else if (service === 'sns' && resource === 'topics') syncAction = 'create_sns_topic'
        else if (service === 'sqs' && resource === 'queues') syncAction = 'create_sqs_queue'
        else if (service === 'secretsmanager' && resource === 'secrets') syncAction = 'create_secret'
        else if (service === 'acm' && resource === 'certificates') syncAction = 'request_certificate'
        else if (service === 'cloudfront' && resource === 'distributions') syncAction = 'create_cloudfront_distribution'
        get()._syncAction(syncAction, syncPayload)
        if (created.pendingTransition) get()._ensureTick()
        return created
      },
      deleteGenericResource: (service, resource, id) => {
        const cfg = genericCfg(service, resource)
        // Transient "deleting" state before removal, if the config declares one.
        if (cfg?.lifecycle?.deleteState) {
          set((s) => mapGeneric(s, service, resource, id, (x) => ({
            ...x,
            status: cfg.lifecycle.deleteState,
            stateTransitionAt: dueIn(GENERIC_TIMING.deleting),
            pendingTransition: { op: 'delete' },
          })))
          get()._ensureTick()
          get()._syncAction('delete_generic_resource', { service, resource, id })
          return ok()
        }
        set((s) => removeGeneric(s, service, resource, id))
        get()._syncAction('delete_generic_resource', { service, resource, id })
        return ok()
      },
      updateGenericResource: (service, resource, id, patch) => {
        set((s) => mapGeneric(s, service, resource, id, (x) => ({ ...x, ...patch })))
        get()._syncAction('update_generic_resource', { service, resource, id, patch: patch || {} })
        return ok()
      },

      // Generic action (reboot/modify/...) driven by cfg.lifecycle.actions.
      transitionGenericResource: (service, resource, id, action, extraPatch) => {
        const cfg = genericCfg(service, resource)
        const spec = cfg?.lifecycle?.actions?.[action]
        if (!spec) return fail(resourceNotFound(`${action}`, `Action '${action}' is not supported for ${service}/${resource}.`))
        set((s) => mapGeneric(s, service, resource, id, (x) => ({
          ...x,
          status: spec.interim,
          stateTransitionAt: dueIn(spec.delayMs || GENERIC_TIMING.action),
          pendingTransition: { op: 'action', final: spec.final, patch: extraPatch || {} },
        })))
        get()._ensureTick()
        return ok()
      },

      // ---------- RDS bespoke ----------
      rebootDb: (id) => {
        const dbs = get().genericResources?.rds?.databases || []
        const db = dbs.find((d) => d.id === id) || dbs[0]
        const res = get().transitionGenericResource('rds', 'databases', id, 'reboot')
        if (db) get()._syncAction('reboot_rds', { id: db.id, name: db.name })
        return res
      },
      modifyDb: (id, patch) => get().transitionGenericResource('rds', 'databases', id, 'modify', patch),

      // ---------- Lambda bespoke ----------
      invokeLambdaFn: (id, payload) => {
        const durationMs = 80 + Math.floor(Math.random() * 400)
        const billedMs = Math.ceil(durationMs / 100) * 100
        const memoryUsed = 60 + Math.floor(Math.random() * 40)
        const entry = { at: new Date().toISOString(), statusCode: 200, durationMs, billedMs, memoryUsed, payload: payload ?? null }
        const funcs = get().genericResources?.lambda?.functions || []
        const fn = funcs.find((f) => f.id === id) || funcs[0]
        set((s) => mapGeneric(s, 'lambda', 'functions', id, (f) => ({
          ...f,
          invocationHistory: [entry, ...((f.invocationHistory) || [])].slice(0, 50),
          invocations_24h: (f.invocations_24h || 0) + 1,
        })))
        if (fn) get()._syncAction('invoke_lambda', { id: fn.id, name: fn.name })
        return { statusCode: 200, body: payload ?? { message: 'Hello from Lambda!' }, durationMs, billedMs, memoryUsed }
      },
      setLambdaCode: (id, code) => {
        const funcs = get().genericResources?.lambda?.functions || []
        const fn = funcs.find((f) => f.id === id) || funcs[0]
        set((s) => mapGeneric(s, 'lambda', 'functions', id, (x) => ({ ...x, code })))
        if (fn) get()._syncAction('update_lambda_code', { id: fn.id, name: fn.name, code })
      },
      setLambdaEnv: (id, env) => {
        const funcs = get().genericResources?.lambda?.functions || []
        const fn = funcs.find((f) => f.id === id) || funcs[0]
        set((s) => mapGeneric(s, 'lambda', 'functions', id, (x) => ({ ...x, env: env || {} })))
        if (fn) get()._syncAction('update_lambda_env', { id: fn.id, name: fn.name, env: env || {} })
      },

      // ---------- SNS / SQS / Secrets / Route53 ----------
      publishSnsTopic: (id, message) => {
        const topics = get().genericResources?.sns?.topics || []
        const topic = topics.find((t) => t.id === id) || topics[0]
        if (!topic) return fail(resourceNotFound('Publish', 'SNS topic not found.'))
        set((s) => mapGeneric(s, 'sns', 'topics', topic.id, (t) => ({
          ...t,
          published: (t.published || 0) + 1,
          lastPublish: new Date().toISOString(),
          lastMessage: message || 'lab notification',
        })))
        get()._syncAction('publish_sns', { id: topic.id, name: topic.name, message: message || 'lab notification' })
        return ok({ topic: topic.name })
      },
      sendSqsMessage: (id, body) => {
        const queues = get().genericResources?.sqs?.queues || []
        const queue = queues.find((q) => q.id === id) || queues[0]
        if (!queue) return fail(resourceNotFound('SendMessage', 'SQS queue not found.'))
        set((s) => mapGeneric(s, 'sqs', 'queues', queue.id, (q) => ({
          ...q,
          messages: (q.messages || 0) + 1,
          lastSend: new Date().toISOString(),
          lastBody: body || 'lab-message',
        })))
        get()._syncAction('send_sqs', { id: queue.id, name: queue.name })
        return ok({ queue: queue.name })
      },
      receiveSqsMessage: (id) => {
        const queues = get().genericResources?.sqs?.queues || []
        const queue = queues.find((q) => q.id === id) || queues[0]
        if (!queue) return fail(resourceNotFound('ReceiveMessage', 'SQS queue not found.'))
        const available = queue.messages || 0
        const took = available > 0 ? 1 : 0
        set((s) => mapGeneric(s, 'sqs', 'queues', queue.id, (q) => ({
          ...q,
          messages: Math.max(0, (q.messages || 0) - took),
          lastReceive: new Date().toISOString(),
        })))
        get()._syncAction('receive_sqs', { id: queue.id, name: queue.name, max: 1 })
        return ok({ count: took, body: took ? (queue.lastBody || 'lab-message') : null })
      },
      purgeSqsQueue: (id) => {
        const queues = get().genericResources?.sqs?.queues || []
        const queue = queues.find((q) => q.id === id) || queues[0]
        if (!queue) return fail(resourceNotFound('PurgeQueue', 'SQS queue not found.'))
        set((s) => mapGeneric(s, 'sqs', 'queues', queue.id, (q) => ({ ...q, messages: 0, lastPurge: new Date().toISOString() })))
        get()._syncAction('purge_sqs', { id: queue.id, name: queue.name })
        return ok()
      },
      getSecretValue: (id) => {
        const secrets = get().genericResources?.secretsmanager?.secrets || []
        const secret = secrets.find((s) => s.id === id) || secrets[0]
        if (!secret) return fail(resourceNotFound('GetSecretValue', 'Secret not found.'))
        const value = secret.secretValue || `lab-secret-${secret.name}`
        set((s) => mapGeneric(s, 'secretsmanager', 'secrets', secret.id, (x) => ({
          ...x, lastAccessed: new Date().toISOString(),
        })))
        get()._syncAction('get_secret_value', { id: secret.id, name: secret.name })
        return ok({ value, name: secret.name })
      },
      rotateSecret: (id) => {
        const secrets = get().genericResources?.secretsmanager?.secrets || []
        const secret = secrets.find((s) => s.id === id) || secrets[0]
        if (!secret) return fail(resourceNotFound('RotateSecret', 'Secret not found.'))
        const next = `rotated-${Math.random().toString(36).slice(2, 8)}`
        set((s) => mapGeneric(s, 'secretsmanager', 'secrets', secret.id, (x) => ({
          ...x,
          rotation: 'Enabled',
          versions: (x.versions || 1) + 1,
          lastChanged: 'Today',
          secretValue: next,
        })))
        get()._syncAction('rotate_secret', { id: secret.id, name: secret.name })
        return ok({ value: next })
      },
      upsertRoute53Record: (zoneId, record) => {
        const zones = get().genericResources?.route53?.['hosted-zones'] || []
        const zone = zones.find((z) => z.id === zoneId) || zones[0]
        if (!zone) return fail(resourceNotFound('ChangeResourceRecordSets', 'Hosted zone not found.'))
        const name = record?.name || 'app.example.internal'
        const type = record?.type || 'A'
        set((s) => mapGeneric(s, 'route53', 'hosted-zones', zone.id, (z) => {
          const records = [...(z.recordSets || [])]
          const idx = records.findIndex((r) => r.name === name && r.type === type)
          const row = { name, type, value: record?.value || '10.0.0.10', ttl: record?.ttl || 300 }
          if (idx >= 0) records[idx] = { ...records[idx], ...row }
          else records.push(row)
          return { ...z, recordSets: records, records: records.length }
        }))
        get()._syncAction('upsert_route53_record', {
          zone_id: zone.id, zone: zone.name, record_name: name, type, value: record?.value, ttl: record?.ttl,
        })
        return ok()
      },

      // ---------- DynamoDB bespoke ----------
      putDynamoItem: (id, item) => {
        const tables = get().genericResources?.dynamodb?.tables || []
        const table = tables.find((t) => t.id === id) || tables[0]
        set((s) => mapGeneric(s, 'dynamodb', 'tables', id, (t) => {
          const records = [...((t.records) || [])]
          const pkField = (t.partitionKey || 'pk').split(' ')[0]
          const skField = (t.sortKey || '').split(' ')[0]
          const idx = records.findIndex((r) => r[pkField] === item[pkField] && (!skField || r[skField] === item[skField]))
          if (idx >= 0) records[idx] = { ...records[idx], ...item }
          else records.push(item)
          return { ...t, records, items: records.length }
        }))
        if (table) get()._syncAction('put_dynamodb_item', { id: table.id, name: table.name, item })
        return ok()
      },
      deleteDynamoItem: (id, key) => {
        const tables = get().genericResources?.dynamodb?.tables || []
        const table = tables.find((t) => t.id === id) || tables[0]
        set((s) => mapGeneric(s, 'dynamodb', 'tables', id, (t) => {
          const pkField = (t.partitionKey || 'pk').split(' ')[0]
          const skField = (t.sortKey || '').split(' ')[0]
          const records = ((t.records) || []).filter((r) => !(r[pkField] === key[pkField] && (!skField || r[skField] === key[skField])))
          return { ...t, records, items: records.length }
        }))
        if (table) get()._syncAction('delete_dynamodb_item', { id: table.id, name: table.name, key })
        return ok()
      },
      queryDynamo: (id, key) => {
        const t = (get().genericResources?.dynamodb?.tables || []).find((x) => x.id === id)
        if (!t) return []
        const pkField = (t.partitionKey || 'pk').split(' ')[0]
        return ((t.records) || []).filter((r) => r[pkField] === key[pkField])
      },
      scanDynamo: (id) => {
        const t = (get().genericResources?.dynamodb?.tables || []).find((x) => x.id === id)
        return t ? ((t.records) || []) : []
      },

      scaleEksResource: (id, patch = {}) => {
        const clusters = get().genericResources?.eks?.clusters || []
        const ngs = get().genericResources?.eks?.['node-groups'] || []
        const cluster = clusters.find((c) => c.id === id)
        const ng = ngs.find((n) => n.id === id)
        const target = cluster || ng
        if (!target) return fail(resourceNotFound('UpdateClusterConfig', 'EKS resource not found.'))
        const resource = cluster ? 'clusters' : 'node-groups'
        const next = { ...patch }
        if (next.nodes != null) next.nodes = Math.max(0, Number(next.nodes))
        if (next.desired != null) next.desired = Math.max(0, Number(next.desired))
        set((s) => mapGeneric(s, 'eks', resource, id, (x) => ({ ...x, ...next })))
        get()._syncAction('scale_eks', { id: target.id, name: target.name, ...next })
        return ok(next)
      },
      scaleEcsService: (id, desired) => {
        const services = get().genericResources?.ecs?.services || []
        const svc = services.find((s) => s.id === id) || services[0]
        if (!svc) return fail(resourceNotFound('UpdateService', 'ECS service not found.'))
        const n = Math.max(0, Number(desired))
        set((s) => mapGeneric(s, 'ecs', 'services', svc.id, (x) => ({ ...x, desired: n, running: n })))
        get()._syncAction('scale_ecs', { id: svc.id, name: svc.name, desired: n })
        return ok({ desired: n })
      },

      // ---------- CloudFormation bespoke ----------
      createCfnStack: (name, template) => {
        const { region } = get()
        // Parse resources out of a (loosely-typed) template object/string.
        let tmpl = template
        if (typeof template === 'string') { try { tmpl = JSON.parse(template) } catch { tmpl = {} } }
        const resEntries = Object.entries((tmpl && tmpl.Resources) || {})
        const outEntries = Object.entries((tmpl && tmpl.Outputs) || {})
        const id = newGenericId('cloudformation', 'stacks')
        const now = new Date().toISOString()
        const resourceList = resEntries.map(([logicalId, def]) => ({ logicalId, type: def?.Type || 'AWS::CloudFormation::CustomResource', physicalId: `${name}-${logicalId}-${Math.random().toString(16).slice(2, 8)}`, status: 'CREATE_IN_PROGRESS' }))
        const outputs = outEntries.map(([key, def]) => ({ key, value: typeof def?.Value === 'string' ? def.Value : JSON.stringify(def?.Value ?? ''), description: def?.Description || '' }))
        const stack = {
          id, region, name, created: now, template: typeof template === 'string' ? template : JSON.stringify(template || {}, null, 2),
          tags: { Environment: 'lab', Project: 'fixitlab' },
          status: 'CREATE_IN_PROGRESS', resources: resourceList.length,
          resourceList,
          outputs,
          events: [{ at: now, logicalId: name, type: 'AWS::CloudFormation::Stack', status: 'CREATE_IN_PROGRESS', reason: 'User Initiated' }],
          stateTransitionAt: dueIn(GENERIC_TIMING.createStep),
          pendingTransition: { op: 'create', states: ['CREATE_IN_PROGRESS', 'CREATE_COMPLETE'], step: 0, delayMs: GENERIC_TIMING.createStep },
        }
        set((s) => ({
          genericResources: {
            ...(s.genericResources || {}),
            cloudformation: {
              ...(s.genericResources?.cloudformation || {}),
              stacks: [...(s.genericResources?.cloudformation?.stacks || []), stack],
            },
          },
        }))
        get()._syncAction('create_cfn_stack', {
          id: stack.id, name: stack.name, resources: stack.resources, template: stack.template, status: stack.status,
        })
        get()._ensureTick()
        return stack
      },

      // ---------- CloudWatch bespoke ----------
      createCwAlarm: ({ name, metric, namespace, threshold, region }) => {
        const alarm = { name, region: region || get().region, metric: metric || 'CPUUtilization', namespace: namespace || 'AWS/EC2', state: 'OK', threshold: threshold || '> 80%' }
        set((s) => ({ cwAlarms: [...(s.cwAlarms || []), alarm] }))
        get()._syncAction('create_cw_alarm', alarm)
        return alarm
      },
      deleteCwAlarm: (name) => {
        set((s) => ({ cwAlarms: (s.cwAlarms || []).filter((a) => a.name !== name) }))
        get()._syncAction('delete_cw_alarm', { name })
        return ok()
      },
      createCwDashboard: ({ name, widgets, region }) => {
        const dash = { name, region: region || get().region, widgets: widgets || 0, created: new Date().toISOString() }
        set((s) => ({ cwDashboards: [...(s.cwDashboards || []), dash] }))
        get()._syncAction('create_cw_dashboard', dash)
        return dash
      },
      deleteCwDashboard: (name) => {
        set((s) => ({ cwDashboards: (s.cwDashboards || []).filter((d) => d.name !== name) }))
        get()._syncAction('delete_cw_dashboard', { name })
        return ok()
      },

      // ---------- IAM engine ----------
      // Gate a mutating action through the current principal's policies.
      can: (action, resource = '*') => evaluate(get().currentPrincipal, action, resource),
      whoami: () => {
        const p = get().currentPrincipal
        return { name: p?.name, arn: p?.arn, userId: p?.userId, type: p?.type }
      },
      assumeRole: (roleName) => {
        const { iamRoles } = get()
        const role = iamRoles.find((r) => r.name === roleName)
        if (!role) {
          const err = resourceNotFound('AssumeRole', `Role with name ${roleName} cannot be found.`)
          get().pushFlash('error', err.str)
          return fail(err)
        }
        const sessionName = 'fixitlab-session'
        set({
          currentPrincipal: {
            type: 'assumed-role',
            name: `${roleName}/${sessionName}`,
            arn: `arn:aws:sts::${ACCOUNT_ID}:assumed-role/${roleName}/${sessionName}`,
            userId: `AROA${roleName.toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 16).padEnd(16, '0')}:${sessionName}`,
            policyNames: role.policies || [],
            policies: policiesFromNames(role.policies || []),
          },
        })
        return ok({ arn: `arn:aws:sts::${ACCOUNT_ID}:assumed-role/${roleName}/${sessionName}` })
      },
      resetPrincipal: () => set({
        currentPrincipal: {
          type: 'user', name: 'admin-user', arn: `arn:aws:iam::${ACCOUNT_ID}:user/admin-user`,
          userId: 'AIDAADMIN0000000ADMIN', policyNames: ['AdministratorAccess'], policies: policiesFromNames(['AdministratorAccess']),
        },
      }),

      // ---------- Console chrome (consumed by chrome UI agent) ----------
      toggleFavorite: (serviceKey) => set((s) => {
        const favs = s.favorites || []
        return { favorites: favs.includes(serviceKey) ? favs.filter((x) => x !== serviceKey) : [...favs, serviceKey] }
      }),
      pushRecentService: (serviceKey) => set((s) => {
        const recents = (s.recentServices || []).filter((x) => x !== serviceKey)
        return { recentServices: [serviceKey, ...recents].slice(0, 12) }
      }),
      setHomeWidgets: (widgets) => set({ homeWidgets: Array.isArray(widgets) ? widgets : [] }),
      updateSettings: (patch) => set((s) => ({ settings: { ...(s.settings || {}), ...(patch || {}) } })),
    }),
    {
      name: 'fixitlab-aws-sim',
      storage: userScopedAwsStorage,
      version: 3,
      // v2 -> v3: new fields get their seeded defaults via merge(); nothing to
      // strip. Provide migrate so zustand does not discard the older payload.
      // Coerce anything that is not a plain object (null / primitive / array
      // from a hand-corrupted blob) to {} so merge() only ever spreads an object.
      migrate: (persistedState) => (
        persistedState && typeof persistedState === 'object' && !Array.isArray(persistedState)
          ? persistedState
          : {}
      ),
      // Persist resource state + region, but not transient flash messages or
      // the active lab session id (that's re-armed fresh by AwsLabOverlay on
      // every mount, never something a stale persisted blob should carry).
      partialize: (s) => {
        const { flash, labSessionId, ...rest } = s
        return rest
      },
      merge: (persisted, current) => {
        // Whole-merge fallback: if any field of a corrupt blob makes the merge
        // throw, fall back to a clean seed rather than crashing rehydrate (which
        // would blow up the console mount → error boundary).
        try {
          return mergePersistedAws(persisted, current)
        } catch {
          return { ...current, ...seedState(), flash: [] }
        }
      },
      // On load/rehydrate: resolve any past-due transitions immediately (no
      // stranded mid-transition resources) and arm the single global tick.
      onRehydrateStorage: () => (state) => {
        if (!state) return
        try {
          state.reconcile()
          state._ensureTick()
        } catch { /* ignore */ }
      },
    },
  ),
)

// Kick the durable lifecycle engine once at module init (covers the very first
// mount before any rehydrate event fires).
try {
  const s = useAwsStore.getState()
  s.reconcile()
  s._ensureTick()
} catch { /* ignore */ }

// ---------- Region-scoped selectors ----------
export const ACCOUNT = ACCOUNT_ID
export const scoped = (arr, region) => (arr || []).filter((x) => !x.region || x.region === region)
