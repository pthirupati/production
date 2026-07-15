// AWS CLI simulation. Parses `aws <service> <command> [flags]` and returns
// realistic JSON/text output backed by the Zustand store. Supports a working
// subset that covers the seeded services; unknown commands return an AWS-style
// error so the terminal stays believable.
import { ACCOUNT } from '../store/awsStore'
import { arn } from '../lib/ids'
import { SERVICE_CONFIGS } from '../pages/generic/serviceConfigs'
import { applyOutput, parseFilters, filterInstances, DRY_RUN_MESSAGE } from '../lib/cliFormat'

function parseFlags(tokens) {
  const flags = {}
  const positional = []
  for (let i = 0; i < tokens.length; i += 1) {
    const t = tokens[i]
    if (t.startsWith('--')) {
      const key = t.slice(2)
      const next = tokens[i + 1]
      // Boolean-only flags never consume a following value.
      if (BOOLEAN_FLAGS.has(key)) { flags[key] = true; continue }
      if (next && !next.startsWith('--')) { flags[key] = next; i += 1 } else { flags[key] = true }
    } else positional.push(t)
  }
  return { flags, positional }
}

// Flags the real CLI treats as valueless switches.
const BOOLEAN_FLAGS = new Set(['dry-run', 'no-cli-pager', 'no-paginate', 'no-verify-ssl'])

// EC2 instance-state -> numeric State.Code (matches the real API).
const EC2_STATE_CODE = { pending: 0, running: 16, 'shutting-down': 32, terminated: 48, stopping: 64, stopped: 80, rebooting: 16 }

// `create-function` -> `CreateFunction` (IAM action-suffix casing).
function pascalCommand(cmd) {
  return String(cmd).split('-').map((p) => p.charAt(0).toUpperCase() + p.slice(1)).join('')
}

const j = (obj) => JSON.stringify(obj, null, 4)

// Deterministic 32-hex ETag keyed on a string, so put-object / list-objects-v2
// return a stable ETag per object (real S3 ETags are the MD5 of the content).
function stableEtag(seed) {
  let h1 = 0x811c9dc5
  let h2 = 0x1000193
  const s = String(seed)
  for (let i = 0; i < s.length; i += 1) {
    const c = s.charCodeAt(i)
    h1 = (h1 ^ c) >>> 0
    h1 = (h1 * 0x01000193) >>> 0
    h2 = ((h2 << 5) + h2 + c) >>> 0
  }
  const hex = (n) => (n >>> 0).toString(16).padStart(8, '0')
  return `"${(hex(h1) + hex(h2) + hex(h1 ^ h2) + hex((h1 + h2) >>> 0)).slice(0, 32)}"`
}

// Split a space-joined `--...-ids`/`--...-groups` value into a token list.
function idList(v) {
  return (v == null || v === true ? '' : String(v)).split(/[\s,]+/).filter(Boolean)
}

// Parse `--tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=web},{Key=Env,Value=dev}]'`
// into a flat { Key: Value } map. Only the Tags portion is used.
function parseTagSpecifications(raw) {
  const tags = {}
  if (!raw || raw === true) return tags
  const re = /\{Key=([^,}]+),Value=([^}]*)\}/g
  let m
  while ((m = re.exec(String(raw))) != null) tags[m[1]] = m[2]
  return tags
}

// Parse `--tags Key=k,Value=v Key=k2,Value=v2` (ec2 create-tags form).
function parseCreateTags(raw) {
  const tags = {}
  if (!raw || raw === true) return tags
  for (const chunk of String(raw).trim().split(/\s+/)) {
    const km = chunk.match(/Key=([^,]+)/)
    const vm = chunk.match(/Value=(.*)$/)
    if (km) tags[km[1]] = vm ? vm[1] : ''
  }
  return tags
}

// Translate known create-* CLI flags into a store payload override for the
// generic resource create path. Only sets keys the user actually passed, so
// cfg.defaults still fill the rest. (createGenericResource merges defaults.)
function knownCreateFlags(serviceKey, resourceKey, flags) {
  const out = {}
  if (serviceKey === 'lambda' && resourceKey === 'functions') {
    if (flags.runtime) out.runtime = String(flags.runtime)
    if (flags['memory-size'] != null && flags['memory-size'] !== true) out.memory = Number(flags['memory-size'])
    if (flags.handler) out.handler = String(flags.handler)
    if (flags.timeout != null && flags.timeout !== true) out.timeout = Number(flags.timeout)
  } else if (serviceKey === 'rds' && resourceKey === 'databases') {
    if (flags.engine) out.engine = String(flags.engine)
    if (flags['db-instance-class']) out.class = String(flags['db-instance-class'])
    if (flags['allocated-storage'] != null && flags['allocated-storage'] !== true) out.storage = Number(flags['allocated-storage'])
  } else if (serviceKey === 'dynamodb' && resourceKey === 'tables') {
    // --key-schema AttributeName=pk,KeyType=HASH AttributeName=sk,KeyType=RANGE
    const ks = flags['key-schema']
    if (ks && ks !== true) {
      const parts = String(ks).trim().split(/\s+/)
      const hash = parts.find((p) => /KeyType=HASH/i.test(p))
      const range = parts.find((p) => /KeyType=RANGE/i.test(p))
      const nameOf = (p) => (p && p.match(/AttributeName=([^,]+)/)?.[1]) || null
      if (nameOf(hash)) out.partitionKey = `${nameOf(hash)} (String)`
      if (nameOf(range)) out.sortKey = `${nameOf(range)} (String)`
    }
  }
  return out
}

// Map the store's structured instance.checks -> describe-instance-status shape.
function checkStatus(checks) {
  const c = checks || {}
  const norm = (v) => (v === 'passed' ? 'ok' : v === 'initializing' ? 'initializing' : v === '-' ? 'not-applicable' : (v || 'initializing'))
  return { system: norm(c.system), instance: norm(c.instance), reachability: c.reachability === 'passed' ? 'passed' : (c.reachability === '-' ? 'failed' : 'initializing') }
}

// IAM gate for a mutating command. Returns an AWS-style denial string when the
// current principal is not allowed to perform `action`, else null. `unauthOp`
// (when set) yields the EC2 UnauthorizedOperation shape instead of AccessDenied.
function iamDeny(store, action, resource, opForMessage, { unauthorized } = {}) {
  const decision = store.can ? store.can(action, resource || '*') : { allowed: true }
  if (decision.allowed) return null
  const who = store.whoami ? store.whoami() : null
  const principalArn = who?.arn || `arn:aws:iam::${ACCOUNT}:user/cli-user`
  if (unauthorized) {
    return `\nAn error occurred (UnauthorizedOperation) when calling the ${opForMessage} operation: You are not authorized to perform this operation. User: ${principalArn} is not authorized to perform: ${action}`
  }
  return `\nAn error occurred (AccessDenied) when calling the ${opForMessage} operation: User: ${principalArn} is not authorized to perform: ${action}`
}

const GENERIC_SERVICE_ALIASES = {
  lambda: 'lambda',
  rds: 'rds',
  dynamodb: 'dynamodb',
  cloudformation: 'cloudformation',
  route53: 'route53',
  sns: 'sns',
  sqs: 'sqs',
  secretsmanager: 'secretsmanager',
  secrets: 'secretsmanager',
  acm: 'acm',
  cloudfront: 'cloudfront',
  eks: 'eks',
  ecs: 'ecs',
  ecr: 'ecr',
  apigateway: 'apigateway',
  'apigatewayv2': 'apigateway',
  events: 'eventbridge',
  eventbridge: 'eventbridge',
  stepfunctions: 'states',
  states: 'states',
  kms: 'kms',
  cloudtrail: 'cloudtrail',
  config: 'config',
  ssm: 'systemsmanager',
  systemsmanager: 'systemsmanager',
  wafv2: 'waf',
  waf: 'waf',
  cognito: 'cognito',
  'cognito-idp': 'cognito',
  elasticache: 'elasticache',
  redshift: 'redshift',
  opensearch: 'opensearch',
  es: 'opensearch',
  kinesis: 'kinesis',
  glue: 'glue',
  athena: 'athena',
}

const GENERIC_COMMANDS = {
  lambda: { functions: { list: 'list-functions', describe: 'get-function', create: 'create-function', delete: 'delete-function', nameFlag: 'function-name', response: 'Functions' } },
  rds: { databases: { list: 'describe-db-instances', describe: 'describe-db-instances', create: 'create-db-instance', delete: 'delete-db-instance', action: 'reboot-db-instance', nameFlag: 'db-instance-identifier', response: 'DBInstances' } },
  dynamodb: { tables: { list: 'list-tables', describe: 'describe-table', create: 'create-table', delete: 'delete-table', nameFlag: 'table-name', response: 'Tables' } },
  cloudformation: { stacks: { list: 'list-stacks', describe: 'describe-stacks', create: 'create-stack', delete: 'delete-stack', nameFlag: 'stack-name', response: 'Stacks' } },
  sns: { topics: { list: 'list-topics', describe: 'get-topic-attributes', create: 'create-topic', delete: 'delete-topic', nameFlag: 'name', response: 'Topics' } },
  sqs: { queues: { list: 'list-queues', describe: 'get-queue-attributes', create: 'create-queue', delete: 'delete-queue', nameFlag: 'queue-name', response: 'QueueUrls' } },
  secretsmanager: { secrets: { list: 'list-secrets', describe: 'describe-secret', create: 'create-secret', delete: 'delete-secret', nameFlag: 'name', response: 'SecretList' } },
  eks: { clusters: { list: 'list-clusters', describe: 'describe-cluster', create: 'create-cluster', delete: 'delete-cluster', nameFlag: 'name', response: 'clusters' } },
  ecs: { clusters: { list: 'list-clusters', describe: 'describe-clusters', create: 'create-cluster', delete: 'delete-cluster', nameFlag: 'cluster-name', response: 'clusterArns' }, services: { list: 'list-services', describe: 'describe-services', create: 'create-service', delete: 'delete-service', nameFlag: 'service-name', response: 'serviceArns' }, tasks: { list: 'list-tasks', describe: 'describe-tasks', create: 'run-task', delete: 'stop-task', nameFlag: 'family', response: 'taskArns' } },
  ecr: { repositories: { list: 'describe-repositories', describe: 'describe-repositories', create: 'create-repository', delete: 'delete-repository', nameFlag: 'repository-name', response: 'repositories' } },
  eventbridge: { rules: { list: 'list-rules', describe: 'describe-rule', create: 'put-rule', delete: 'delete-rule', nameFlag: 'name', response: 'Rules' } },
  states: { 'state-machines': { list: 'list-state-machines', describe: 'describe-state-machine', create: 'create-state-machine', delete: 'delete-state-machine', nameFlag: 'name', response: 'stateMachines' } },
  glue: { jobs: { list: 'list-jobs', describe: 'get-job', create: 'create-job', delete: 'delete-job', nameFlag: 'name', response: 'JobNames' }, databases: { list: 'get-databases', describe: 'get-database', create: 'create-database', delete: 'delete-database', nameFlag: 'name', response: 'DatabaseList' } },
  kinesis: { streams: { list: 'list-streams', describe: 'describe-stream', create: 'create-stream', delete: 'delete-stream', nameFlag: 'stream-name', response: 'StreamNames' } },
  athena: { workgroups: { list: 'list-work-groups', describe: 'get-work-group', create: 'create-work-group', delete: 'delete-work-group', nameFlag: 'name', response: 'WorkGroups' } },
}

function genericResourceArn(serviceKey, resourceKey, row, region, cfg) {
  if (cfg.arnService === 'cloudfront' || cfg.arnService === 'route53') {
    return `arn:aws:${cfg.arnService}::${ACCOUNT}:${cfg.arnResource(row)}`
  }
  return arn(cfg.arnService || serviceKey, region, ACCOUNT, cfg.arnResource ? cfg.arnResource(row) : `${resourceKey}/${row.name}`)
}

function pickResourceName(flags, spec) {
  const candidates = [
    spec.nameFlag,
    'name',
    'id',
    'resource-name',
    'function-name',
    'table-name',
    'queue-name',
    'topic-name',
    'cluster-name',
    'repository-name',
    'db-instance-identifier',
    'stack-name',
  ].filter(Boolean)
  return candidates.map((k) => flags[k]).find(Boolean)
}

function rowToGenericCli(serviceKey, resourceKey, row, region, cfg) {
  return {
    Name: row.name,
    Id: row.id,
    Arn: genericResourceArn(serviceKey, resourceKey, row, region, cfg),
    Region: row.region || region,
    Status: row.status || 'Active',
    Created: row.created,
    Tags: row.tags || {},
    ...row,
  }
}

export function awsCli(argv, store, ctx = {}) {
  const [service, command, ...rest] = argv
  const { flags } = parseFlags(rest)
  const region = flags.region || ctx.region || store.region
  // Run the command, then apply --query / --output as a post-processing pass.
  const result = runCommand(service, command, rest, flags, region, store)
  return applyOutput(result, flags)
}

function runCommand(service, command, rest, flags, region, store) {
  if (!service || service === 'help') {
    return 'usage: aws [options] <command> <subcommand> [parameters]\nTo see help text, you can run:\n  aws help\n  aws <command> help'
  }

  // --- STS ---
  if (service === 'sts' && command === 'get-caller-identity') {
    const who = store.whoami ? store.whoami() : null
    return j({ UserId: who?.userId || 'AIDAEXAMPLEUSERID', Account: ACCOUNT, Arn: who?.arn || arn('iam', region, ACCOUNT, 'user/cli-user') })
  }
  if (service === 'sts' && command === 'assume-role') {
    const roleArn = String(flags['role-arn'] || '')
    const roleName = roleArn.split('/').pop() || flags['role-name']
    if (!roleName) return '\nAn error occurred (ValidationError) when calling the AssumeRole operation: Missing required parameter RoleArn'
    const res = store.assumeRole ? store.assumeRole(roleName) : { ok: false, error: 'assumeRole unavailable' }
    if (res && res.ok === false) return `\n${res.error}`
    const who = store.whoami ? store.whoami() : {}
    return j({
      Credentials: {
        AccessKeyId: 'ASIAIOSFODNN7EXAMPLE',
        SecretAccessKey: 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY',
        SessionToken: 'FQoGZXIvYXdzEExampleSessionToken',
        Expiration: new Date(Date.now() + 3600000).toISOString(),
      },
      AssumedRoleUser: { AssumedRoleId: who?.userId || 'AROAEXAMPLE:fixitlab-session', Arn: who?.arn || res.arn },
    })
  }
  if (service === 'configure' && command === 'list') {
    return '      Name                    Value             Type    Location\n      ----                    -----             ----    --------\n   profile                <not set>             None    None\naccess_key     ****************MPLE shared-credentials-file\nsecret_key     ****************EKEY shared-credentials-file\n    region                 ' + region + '      config-file    ~/.aws/config'
  }
  if (service === 'configure' && command === 'get') {
    const key = rest[0]
    if (key === 'region' || key === 'default.region') return region
    if (key === 'aws_access_key_id') return 'AKIAIOSFODNN7EXAMPLE'
    if (key === 'aws_secret_access_key') return 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY'
    return ''
  }
  if (service === 'configure' && command === 'set') {
    return ''
  }

  // --- EC2 ---
  if (service === 'ec2') {
    const instances = store.instances.filter((i) => i.region === region)
    // Helper: apply IAM gate + --dry-run for a mutating EC2 op.
    const guardEc2 = (action, op, resource) => {
      const denied = iamDeny(store, action, resource, op, { unauthorized: true })
      if (denied) return denied
      if (flags['dry-run']) return DRY_RUN_MESSAGE(op)
      return null
    }
    const instanceToApi = (i) => ({
      InstanceId: i.id, InstanceType: i.type, State: { Code: EC2_STATE_CODE[i.state] ?? 16, Name: i.state },
      PrivateIpAddress: i.privateIp, PublicIpAddress: i.publicIp || undefined,
      ImageId: i.amiId, KeyName: i.keyName, LaunchTime: i.launchTime,
      Placement: { AvailabilityZone: i.az, Tenancy: i.tenancy },
      SubnetId: i.subnetId, VpcId: i.vpcId, Architecture: i.architecture,
      SecurityGroups: (i.securityGroups || []).map((g) => ({ GroupId: g })),
      Tags: Object.entries(i.tags || {}).map(([Key, Value]) => ({ Key, Value })),
    })

    if (command === 'describe-instances') {
      const filters = parseFilters(flags.filters)
      let matched = filterInstances(instances, filters)
      const idFilter = idList(flags['instance-ids'])
      if (idFilter.length) matched = matched.filter((i) => idFilter.includes(i.id))
      const reservations = matched.map((i) => ({
        Groups: [],
        Instances: [instanceToApi(i)],
        OwnerId: ACCOUNT, ReservationId: `r-0${Math.random().toString(16).slice(2, 18)}`,
      }))
      return j({ Reservations: reservations })
    }
    if (command === 'describe-instance-status') {
      const idFilter = idList(flags['instance-ids'])
      const includeAll = flags['include-all-instances'] === true || String(flags['include-all-instances']) === 'true'
      let matched = instances
      if (idFilter.length) matched = matched.filter((i) => idFilter.includes(i.id))
      if (!includeAll) matched = matched.filter((i) => i.state === 'running')
      return j({ InstanceStatuses: matched.map((i) => {
        const cs = checkStatus(i.checks)
        return {
          InstanceId: i.id, AvailabilityZone: i.az,
          InstanceState: { Code: EC2_STATE_CODE[i.state] ?? 16, Name: i.state },
          SystemStatus: { Status: cs.system, Details: [{ Name: 'reachability', Status: cs.reachability }] },
          InstanceStatus: { Status: cs.instance, Details: [{ Name: 'reachability', Status: cs.reachability }] },
        }
      }) })
    }
    if (command === 'run-instances') {
      const guard = guardEc2('ec2:RunInstances', 'RunInstances')
      if (guard) return guard
      const tagMap = parseTagSpecifications(flags['tag-specifications'])
      const count = Number(flags.count) || 1
      const created = store.launchInstances({
        name: tagMap.Name || '',
        amiId: flags['image-id'] || 'ami-0c02fb55956c7d316',
        type: flags['instance-type'] || 't2.micro',
        count,
        keyName: flags['key-name'] || '',
        subnetId: flags['subnet-id'] || '',
        securityGroups: idList(flags['security-group-ids']),
        monitoring: false,
        tags: tagMap,
      })
      const rows = Array.isArray(created) ? created : []
      return j({
        ReservationId: `r-0${Math.random().toString(16).slice(2, 18)}`,
        OwnerId: ACCOUNT,
        Groups: [],
        Instances: rows.map((i) => ({ ...instanceToApi(i), State: { Code: 0, Name: 'pending' } })),
      })
    }
    if (['start-instances', 'stop-instances', 'reboot-instances', 'terminate-instances'].includes(command)) {
      const action = command.replace('-instances', '')
      const actionMap = { start: 'ec2:StartInstances', stop: 'ec2:StopInstances', reboot: 'ec2:RebootInstances', terminate: 'ec2:TerminateInstances' }
      const opMap = { start: 'StartInstances', stop: 'StopInstances', reboot: 'RebootInstances', terminate: 'TerminateInstances' }
      const guard = guardEc2(actionMap[action], opMap[action])
      if (guard) return guard
      const ids = idList(flags['instance-ids'])
      const res = store.instanceAction(ids, action)
      if (res && res.ok === false && res.error) return `\n${res.error}`
      const key = { start: 'StartingInstances', stop: 'StoppingInstances', reboot: null, terminate: 'TerminatingInstances' }[action]
      if (action === 'reboot') return ''
      return j({ [key]: ids.map((id) => ({ InstanceId: id, CurrentState: { Name: action === 'start' ? 'pending' : action === 'stop' ? 'stopping' : 'shutting-down' }, PreviousState: { Name: 'running' } })) })
    }
    if (command === 'create-tags') {
      const guard = guardEc2('ec2:CreateTags', 'CreateTags')
      if (guard) return guard
      const ids = idList(flags.resources)
      const tags = parseCreateTags(flags.tags)
      // The store only exposes a Name-tag setter for instances (used by the
      // console rename flow); apply Name so CLI + GUI stay in sync. Other tag
      // keys are accepted silently, matching the real CLI's empty success.
      if (tags.Name && store.setInstanceName) {
        for (const id of ids) {
          if (store.instances.find((x) => x.id === id)) store.setInstanceName(id, tags.Name)
        }
      }
      return ''
    }
    if (command === 'create-key-pair') {
      const guard = guardEc2('ec2:CreateKeyPair', 'CreateKeyPair')
      if (guard) return guard
      const name = flags['key-name']
      if (!name) return '\nAn error occurred (MissingParameter) when calling the CreateKeyPair operation: The request must contain the parameter KeyName'
      const kp = store.createKeyPair({ name, type: flags['key-type'] || 'rsa' })
      const pem = ['-----BEGIN RSA PRIVATE KEY-----',
        'MIIEowIBAAKCAQEArandomsimulatedkeymaterialforfixitlabdemoonly000000',
        'ThisIsASimulatedKeyPairAndContainsNoRealCryptographicMaterialAtAll00',
        '-----END RSA PRIVATE KEY-----'].join('\n')
      return j({ KeyName: kp.name, KeyPairId: kp.id, KeyFingerprint: kp.fingerprint, KeyMaterial: pem })
    }
    if (command === 'create-security-group') {
      const guard = guardEc2('ec2:CreateSecurityGroup', 'CreateSecurityGroup')
      if (guard) return guard
      const name = flags['group-name']
      if (!name) return '\nAn error occurred (MissingParameter) when calling the CreateSecurityGroup operation: The request must contain the parameter GroupName'
      const vpcId = flags['vpc-id'] || store.vpcs.find((v) => v.region === region && v.isDefault)?.id || store.vpcs[0]?.id
      const sg = store.createSecurityGroup({ name, description: flags.description || name, vpcId, inbound: [] })
      if (sg && sg.ok === false) return `\n${sg.error}`
      return j({ GroupId: sg.id })
    }
    if (command === 'authorize-security-group-ingress' || command === 'authorize-security-group-egress') {
      const egress = command.endsWith('egress')
      const op = egress ? 'AuthorizeSecurityGroupEgress' : 'AuthorizeSecurityGroupIngress'
      const guard = guardEc2(egress ? 'ec2:AuthorizeSecurityGroupEgress' : 'ec2:AuthorizeSecurityGroupIngress', op)
      if (guard) return guard
      const id = flags['group-id']
      const sg = store.securityGroups.find((s) => s.id === id)
      if (!sg) return `\nAn error occurred (InvalidGroup.NotFound) when calling the ${op} operation: The security group '${id}' does not exist`
      const rule = {
        type: flags.protocol === 'tcp' && String(flags.port) === '22' ? 'SSH' : 'Custom',
        protocol: (flags.protocol || 'tcp').toUpperCase(),
        from: Number(flags.port) || 0, to: Number(flags.port) || 0,
        source: flags.cidr || '0.0.0.0/0', description: '',
      }
      store.addSgRule(id, egress ? 'outbound' : 'inbound', rule)
      return ''
    }
    if (command === 'revoke-security-group-ingress' || command === 'revoke-security-group-egress') {
      const egress = command.endsWith('egress')
      const op = egress ? 'RevokeSecurityGroupEgress' : 'RevokeSecurityGroupIngress'
      const guard = guardEc2(egress ? 'ec2:RevokeSecurityGroupEgress' : 'ec2:RevokeSecurityGroupIngress', op)
      if (guard) return guard
      const id = flags['group-id']
      const sg = store.securityGroups.find((s) => s.id === id)
      if (!sg) return `\nAn error occurred (InvalidGroup.NotFound) when calling the ${op} operation: The security group '${id}' does not exist`
      const dir = egress ? 'outbound' : 'inbound'
      const port = Number(flags.port)
      const cidr = flags.cidr
      const kept = (sg[dir] || []).filter((r) => !((Number.isNaN(port) || r.from === port) && (!cidr || r.source === cidr)))
      store.setSgRules(id, dir, kept)
      return ''
    }
    if (command === 'delete-security-group') {
      const guard = guardEc2('ec2:DeleteSecurityGroup', 'DeleteSecurityGroup')
      if (guard) return guard
      const res = store.deleteSecurityGroup(flags['group-id'])
      if (res && res.ok === false) return `\n${res.error}`
      return ''
    }
    if (command === 'create-vpc') {
      const guard = guardEc2('ec2:CreateVpc', 'CreateVpc')
      if (guard) return guard
      const vpc = store.createVpc({ cidr: flags['cidr-block'], tenancy: flags['instance-tenancy'] })
      if (vpc && vpc.ok === false) return `\n${vpc.error}`
      return j({ Vpc: { VpcId: vpc.id, CidrBlock: vpc.cidr, State: vpc.state, IsDefault: vpc.isDefault, InstanceTenancy: vpc.tenancy, OwnerId: ACCOUNT } })
    }
    if (command === 'delete-vpc') {
      const guard = guardEc2('ec2:DeleteVpc', 'DeleteVpc')
      if (guard) return guard
      const res = store.deleteVpc(flags['vpc-id'])
      if (res && res.ok === false) return `\n${res.error}`
      return ''
    }
    if (command === 'create-subnet') {
      const guard = guardEc2('ec2:CreateSubnet', 'CreateSubnet')
      if (guard) return guard
      const subnet = store.createSubnet({ vpcId: flags['vpc-id'], cidr: flags['cidr-block'], az: flags['availability-zone'] })
      if (subnet && subnet.ok === false) return `\n${subnet.error}`
      return j({ Subnet: { SubnetId: subnet.id, VpcId: subnet.vpcId, CidrBlock: subnet.cidr, AvailabilityZone: subnet.az, AvailableIpAddressCount: subnet.availableIps, MapPublicIpOnLaunch: subnet.mapPublicIp, State: 'available' } })
    }
    if (command === 'delete-subnet') {
      const guard = guardEc2('ec2:DeleteSubnet', 'DeleteSubnet')
      if (guard) return guard
      const res = store.deleteSubnet(flags['subnet-id'])
      if (res && res.ok === false) return `\n${res.error}`
      return ''
    }
    if (command === 'allocate-address') {
      const guard = guardEc2('ec2:AllocateAddress', 'AllocateAddress')
      if (guard) return guard
      const eip = store.allocateEip()
      return j({ PublicIp: eip.publicIp, AllocationId: eip.allocationId, Domain: eip.domain })
    }
    if (command === 'associate-address') {
      const guard = guardEc2('ec2:AssociateAddress', 'AssociateAddress')
      if (guard) return guard
      const res = store.associateEip(flags['allocation-id'], flags['instance-id'])
      if (res && res.ok === false) return `\n${res.error}`
      const eip = store.elasticIps.find((e) => e.allocationId === flags['allocation-id'])
      return j({ AssociationId: eip?.associationId })
    }
    if (command === 'disassociate-address') {
      const guard = guardEc2('ec2:DisassociateAddress', 'DisassociateAddress')
      if (guard) return guard
      const alloc = flags['allocation-id'] || store.elasticIps.find((e) => e.associationId === flags['association-id'])?.allocationId
      store.disassociateEip(alloc)
      return ''
    }
    if (command === 'release-address') {
      const guard = guardEc2('ec2:ReleaseAddress', 'ReleaseAddress')
      if (guard) return guard
      const res = store.releaseEip(flags['allocation-id'])
      if (res && res.ok === false) return `\n${res.error}`
      return ''
    }
    if (command === 'describe-addresses') {
      return j({ Addresses: (store.elasticIps || []).filter((e) => !e.region || e.region === region).map((e) => ({ PublicIp: e.publicIp, AllocationId: e.allocationId, AssociationId: e.associationId || undefined, InstanceId: e.instanceId || undefined, Domain: e.domain })) })
    }
    if (command === 'attach-volume') {
      const guard = guardEc2('ec2:AttachVolume', 'AttachVolume')
      if (guard) return guard
      const res = store.attachVolume(flags['volume-id'], flags['instance-id'], flags.device)
      if (res && res.ok === false) return `\n${res.error}`
      return j({ VolumeId: flags['volume-id'], InstanceId: flags['instance-id'], Device: flags.device, State: 'attaching' })
    }
    if (command === 'detach-volume') {
      const guard = guardEc2('ec2:DetachVolume', 'DetachVolume')
      if (guard) return guard
      const res = store.detachVolume(flags['volume-id'])
      if (res && res.ok === false) return `\n${res.error}`
      return j({ VolumeId: flags['volume-id'], State: 'detaching' })
    }
    if (command === 'create-snapshot') {
      const guard = guardEc2('ec2:CreateSnapshot', 'CreateSnapshot')
      if (guard) return guard
      const snap = store.createSnapshot(flags['volume-id'], flags.description)
      if (snap && snap.ok === false) return `\n${snap.error}`
      return j({ SnapshotId: snap.id, VolumeId: snap.volumeId, State: snap.state, VolumeSize: snap.size, Progress: snap.progress, Description: snap.description, Encrypted: snap.encrypted, StartTime: snap.started })
    }
    if (command === 'describe-security-groups') {
      return j({ SecurityGroups: store.securityGroups.filter((s) => s.region === region).map((s) => ({ GroupId: s.id, GroupName: s.name, Description: s.description, VpcId: s.vpcId, OwnerId: ACCOUNT })) })
    }
    if (command === 'describe-vpcs') {
      return j({ Vpcs: store.vpcs.filter((v) => v.region === region).map((v) => ({ VpcId: v.id, CidrBlock: v.cidr, State: v.state, IsDefault: v.isDefault, OwnerId: ACCOUNT })) })
    }
    if (command === 'describe-subnets') {
      return j({ Subnets: store.subnets.filter((s) => s.region === region).map((s) => ({ SubnetId: s.id, VpcId: s.vpcId, CidrBlock: s.cidr, AvailabilityZone: s.az, AvailableIpAddressCount: s.availableIps, MapPublicIpOnLaunch: s.mapPublicIp })) })
    }
    if (command === 'describe-volumes') {
      return j({ Volumes: store.volumes.filter((v) => v.region === region).map((v) => ({ VolumeId: v.id, Size: v.size, VolumeType: v.type, State: v.state, AvailabilityZone: v.az, Encrypted: v.encrypted, Attachments: v.attachedTo ? [{ InstanceId: v.attachedTo, Device: v.device, State: 'attached' }] : [] })) })
    }
    if (command === 'describe-snapshots') {
      return j({ Snapshots: (store.snapshots || []).filter((s) => !s.region || s.region === region).map((s) => ({ SnapshotId: s.id, VolumeId: s.volumeId, State: s.state, VolumeSize: s.size, Progress: s.progress, Description: s.description, Encrypted: s.encrypted, StartTime: s.started })) })
    }
    if (command === 'describe-key-pairs') {
      return j({ KeyPairs: store.keyPairs.filter((k) => k.region === region).map((k) => ({ KeyPairId: k.id, KeyName: k.name, KeyType: k.type, KeyFingerprint: k.fingerprint })) })
    }
    if (command === 'describe-images') {
      return j({ Images: store.amis.filter((a) => a.region === region).map((a) => ({ ImageId: a.id, Name: a.name, Description: a.desc, Architecture: a.arch, OwnerId: a.owner, State: 'available' })) })
    }
    return `\nAn error occurred (InvalidAction) when calling the ${command} operation: aws ec2 ${command} is not yet simulated.`
  }

  // --- S3 (high-level) ---
  if (service === 's3') {
    if (command === 'ls') {
      const target = rest.find((t) => t.startsWith('s3://'))
      if (!target) {
        return store.s3Buckets.map((b) => `${new Date(b.created).toISOString().replace('T', ' ').slice(0, 19)} ${b.name}`).join('\n')
      }
      const bucketName = target.replace('s3://', '').split('/')[0]
      const prefix = target.replace('s3://', '').split('/').slice(1).join('/')
      const bucket = store.s3Buckets.find((b) => b.name === bucketName)
      if (!bucket) return `\nAn error occurred (NoSuchBucket) when calling the ListObjectsV2 operation: The specified bucket does not exist`
      return bucket.objects.filter((o) => o.key.startsWith(prefix)).map((o) => `${new Date(o.modified).toISOString().replace('T', ' ').slice(0, 19)} ${String(o.size).padStart(10)} ${o.key}`).join('\n') || ''
    }
    if (command === 'mb') {
      const name = (rest[0] || '').replace('s3://', '')
      if (!name) return 'usage: aws s3 mb <S3Uri>'
      store.createBucket({ name, region, blockPublic: true })
      return `make_bucket: ${name}`
    }
    if (command === 'rb') {
      const name = (rest[0] || '').replace('s3://', '')
      store.deleteBucket(name)
      return `remove_bucket: ${name}`
    }
    if (command === 'cp') {
      const [src, dest] = rest
      const s3Target = [src, dest].find((x) => String(x || '').startsWith('s3://'))
      if (!s3Target) return 'usage: aws s3 cp <LocalPath> <S3Uri> or <S3Uri> <LocalPath>'
      const [bucketName, ...keyParts] = s3Target.replace('s3://', '').split('/')
      const key = keyParts.join('/') || String(src || 'upload.bin').split('/').pop()
      const bucket = store.s3Buckets.find((b) => b.name === bucketName)
      if (!bucket) return `\nAn error occurred (NoSuchBucket) when calling the PutObject operation: The specified bucket does not exist`
      if (String(src || '').startsWith('s3://')) return `download: ${src} to ./${key.split('/').pop()}`
      store.putObject(bucketName, key, 2048)
      return `upload: ${src} to s3://${bucketName}/${key}`
    }
    return `aws s3 ${command}: simulated high-level command`
  }
  if (service === 's3api') {
    const bucket = flags.bucket ? store.s3Buckets.find((b) => b.name === flags.bucket) : null
    if (command === 'list-buckets') {
      return j({ Buckets: store.s3Buckets.map((b) => ({ Name: b.name, CreationDate: b.created })), Owner: { DisplayName: store.account.alias, ID: ACCOUNT } })
    }
    if (command === 'create-bucket') {
      if (!flags.bucket) return '\nAn error occurred (InvalidBucketName) when calling the CreateBucket operation: Missing required parameter Bucket'
      const created = store.createBucket({ name: flags.bucket, region, blockPublic: true })
      return j({ Location: region === 'us-east-1' ? `/${created.name}` : `http://${created.name}.s3.${region}.amazonaws.com/` })
    }
    if (command === 'delete-bucket') {
      if (!flags.bucket) return '\nAn error occurred (InvalidBucketName) when calling the DeleteBucket operation: Missing required parameter Bucket'
      store.deleteBucket(flags.bucket)
      return ''
    }
    if (command === 'list-objects-v2') {
      if (!bucket) return '\nAn error occurred (NoSuchBucket) when calling the ListObjectsV2 operation: The specified bucket does not exist'
      const prefix = flags.prefix || ''
      const contents = bucket.objects.filter((o) => o.key.startsWith(prefix)).map((o) => ({
        Key: o.key, LastModified: o.modified, ETag: o.etag || stableEtag(`${bucket.name}/${o.key}`), Size: o.size, StorageClass: o.storageClass || 'STANDARD',
      }))
      return j({ Contents: contents, Name: bucket.name, Prefix: prefix, KeyCount: contents.length, MaxKeys: 1000, IsTruncated: false })
    }
    if (command === 'put-object') {
      if (!flags.bucket || !flags.key) return '\nAn error occurred (ValidationError) when calling the PutObject operation: Missing required bucket/key'
      store.putObject(flags.bucket, flags.key, flags.body ? 1024 : 0)
      return j({ ETag: stableEtag(`${flags.bucket}/${flags.key}`), ServerSideEncryption: 'AES256' })
    }
    if (command === 'delete-object') {
      if (!flags.bucket || !flags.key) return '\nAn error occurred (ValidationError) when calling the DeleteObject operation: Missing required bucket/key'
      store.deleteObject(flags.bucket, flags.key)
      return j({})
    }
    if (command === 'get-bucket-versioning') {
      if (!bucket) return '\nAn error occurred (NoSuchBucket) when calling the GetBucketVersioning operation: The specified bucket does not exist'
      return bucket.versioning ? j({ Status: 'Enabled' }) : j({})
    }
    if (command === 'put-bucket-versioning') {
      if (!bucket) return '\nAn error occurred (NoSuchBucket) when calling the PutBucketVersioning operation: The specified bucket does not exist'
      const enabled = String(flags['versioning-configuration'] || '').includes('Enabled') || flags.status === 'Enabled'
      store.updateBucket(flags.bucket, { versioning: enabled })
      return ''
    }
    if (command === 'get-public-access-block') {
      if (!bucket) return '\nAn error occurred (NoSuchPublicAccessBlockConfiguration) when calling the GetPublicAccessBlock operation: The public access block configuration was not found'
      const blocked = bucket.publicAccess?.includes('not public')
      return j({ PublicAccessBlockConfiguration: { BlockPublicAcls: blocked, IgnorePublicAcls: blocked, BlockPublicPolicy: blocked, RestrictPublicBuckets: blocked } })
    }
    if (command === 'put-public-access-block') {
      if (!bucket) return '\nAn error occurred (NoSuchBucket) when calling the PutPublicAccessBlock operation: The specified bucket does not exist'
      const text = String(flags['public-access-block-configuration'] || '')
      const blocked = !text || !/false/i.test(text)
      store.updateBucket(flags.bucket, { publicAccess: blocked ? 'Bucket and objects not public' : 'Objects can be public' })
      return ''
    }
    if (command === 'get-bucket-policy') {
      if (!bucket) return '\nAn error occurred (NoSuchBucket) when calling the GetBucketPolicy operation: The specified bucket does not exist'
      if (!bucket.bucketPolicy) return '\nAn error occurred (NoSuchBucketPolicy) when calling the GetBucketPolicy operation: The bucket policy does not exist'
      return j({ Policy: bucket.bucketPolicy })
    }
    if (command === 'put-bucket-policy') {
      if (!bucket) return '\nAn error occurred (NoSuchBucket) when calling the PutBucketPolicy operation: The specified bucket does not exist'
      store.updateBucket(flags.bucket, { bucketPolicy: flags.policy || '{"Version":"2012-10-17","Statement":[]}' })
      return ''
    }
    if (command === 'delete-bucket-policy') {
      if (!bucket) return '\nAn error occurred (NoSuchBucket) when calling the DeleteBucketPolicy operation: The specified bucket does not exist'
      store.updateBucket(flags.bucket, { bucketPolicy: '' })
      return ''
    }
    if (command === 'get-bucket-cors') {
      if (!bucket) return '\nAn error occurred (NoSuchBucket) when calling the GetBucketCors operation: The specified bucket does not exist'
      if (!bucket.cors) return '\nAn error occurred (NoSuchCORSConfiguration) when calling the GetBucketCors operation: The CORS configuration does not exist'
      return bucket.cors
    }
    if (command === 'put-bucket-cors') {
      if (!bucket) return '\nAn error occurred (NoSuchBucket) when calling the PutBucketCors operation: The specified bucket does not exist'
      store.updateBucket(flags.bucket, { cors: flags['cors-configuration'] || '[]' })
      return ''
    }
    if (command === 'get-bucket-acl') {
      if (!bucket) return '\nAn error occurred (NoSuchBucket) when calling the GetBucketAcl operation: The specified bucket does not exist'
      return j({ Owner: { DisplayName: store.account.alias, ID: ACCOUNT }, Grants: [{ Grantee: { Type: 'CanonicalUser', ID: ACCOUNT }, Permission: bucket.acl === 'Public read' ? 'READ' : 'FULL_CONTROL' }] })
    }
    if (command === 'get-bucket-encryption') {
      if (!bucket) return '\nAn error occurred (NoSuchBucket) when calling the GetBucketEncryption operation: The specified bucket does not exist'
      return j({ ServerSideEncryptionConfiguration: { Rules: [{ ApplyServerSideEncryptionByDefault: { SSEAlgorithm: bucket.encryption === 'SSE-KMS' ? 'aws:kms' : 'AES256' }, BucketKeyEnabled: true }] } })
    }
    if (command === 'put-bucket-encryption') {
      if (!bucket) return '\nAn error occurred (NoSuchBucket) when calling the PutBucketEncryption operation: The specified bucket does not exist'
      const conf = String(flags['server-side-encryption-configuration'] || '')
      store.updateBucket(flags.bucket, { encryption: conf.includes('aws:kms') ? 'SSE-KMS' : 'SSE-S3' })
      return ''
    }
    if (command === 'get-bucket-website') {
      if (!bucket || !bucket.website) return '\nAn error occurred (NoSuchWebsiteConfiguration) when calling the GetBucketWebsite operation: The specified bucket does not have a website configuration'
      return j({ IndexDocument: { Suffix: 'index.html' }, ErrorDocument: { Key: 'error.html' } })
    }
    if (command === 'put-bucket-website') {
      if (!bucket) return '\nAn error occurred (NoSuchBucket) when calling the PutBucketWebsite operation: The specified bucket does not exist'
      store.updateBucket(flags.bucket, { website: true })
      return ''
    }
    return `\nAn error occurred (InvalidAction) when calling the ${command} operation: aws s3api ${command} is not yet simulated.`
  }

  // --- IAM ---
  if (service === 'iam') {
    if (command === 'list-users') return j({ Users: store.iamUsers.map((u) => ({ UserName: u.name, UserId: u.id, Arn: arn('iam', region, ACCOUNT, `user/${u.name}`), CreateDate: u.created })) })
    if (command === 'get-user') {
      const name = flags['user-name'] || store.iamUsers[0]?.name
      const u = store.iamUsers.find((x) => x.name === name)
      if (!u) return '\nAn error occurred (NoSuchEntity) when calling the GetUser operation: The user with name cannot be found.'
      return j({ User: { UserName: u.name, UserId: u.id, Arn: arn('iam', region, ACCOUNT, `user/${u.name}`), CreateDate: u.created } })
    }
    if (command === 'create-user') {
      if (!flags['user-name']) return '\nAn error occurred (ValidationError) when calling the CreateUser operation: Missing required parameter UserName'
      const u = store.createIamUser({ name: flags['user-name'], consoleAccess: false, policies: [] })
      return j({ User: { UserName: u.name, UserId: u.id, Arn: arn('iam', region, ACCOUNT, `user/${u.name}`), CreateDate: u.created } })
    }
    if (command === 'delete-user') {
      if (!flags['user-name']) return '\nAn error occurred (ValidationError) when calling the DeleteUser operation: Missing required parameter UserName'
      store.deleteIamUser(flags['user-name'])
      return ''
    }
    if (command === 'list-roles') return j({ Roles: store.iamRoles.map((r) => ({ RoleName: r.name, RoleId: r.id, Arn: arn('iam', region, ACCOUNT, `role/${r.name}`), CreateDate: r.created })) })
    if (command === 'list-groups') return j({ Groups: store.iamGroups.map((g) => ({ GroupName: g.name, GroupId: g.id, Arn: arn('iam', region, ACCOUNT, `group/${g.name}`) })) })
    if (command === 'list-policies') return j({ Policies: store.iamPolicies.map((p) => ({ PolicyName: p.name, Arn: p.type === 'AWS managed' ? arn('iam', region, 'aws', `policy/${p.name}`) : arn('iam', region, ACCOUNT, `policy/${p.name}`), AttachmentCount: p.attached || 0, CreateDate: p.created, Description: p.description })) })
    if (command === 'create-access-key') {
      const name = flags['user-name']
      if (!name) return '\nAn error occurred (ValidationError) when calling the CreateAccessKey operation: Missing required parameter UserName'
      const key = store.createAccessKey(name)
      return j({ AccessKey: { UserName: name, AccessKeyId: key.id, Status: key.status, SecretAccessKey: key.secret, CreateDate: key.created } })
    }
    if (command === 'list-access-keys') {
      const name = flags['user-name']
      const u = store.iamUsers.find((x) => x.name === name)
      if (!u) return '\nAn error occurred (NoSuchEntity) when calling the ListAccessKeys operation: The user with name cannot be found.'
      return j({ AccessKeyMetadata: u.accessKeys.map((k) => ({ UserName: name, AccessKeyId: k.id, Status: k.status, CreateDate: k.created })) })
    }
    return `\nAn error occurred (InvalidAction) when calling the ${command} operation: aws iam ${command} is not yet simulated.`
  }

  // --- CloudWatch / Logs ---
  if (service === 'cloudwatch') {
    const alarms = store.cwAlarms.filter((a) => !a.region || a.region === region)
    if (command === 'describe-alarms') {
      const names = flags['alarm-names'] ? String(flags['alarm-names']).split(/\s+/) : null
      const state = flags['state-value']
      const filtered = alarms.filter((a) => (!names || names.includes(a.name)) && (!state || a.state === state))
      return j({ MetricAlarms: filtered.map((a) => ({ AlarmName: a.name, AlarmArn: arn('cloudwatch', region, ACCOUNT, `alarm:${a.name}`), AlarmDescription: a.threshold, StateValue: a.state, MetricName: a.metric, Namespace: a.namespace, Threshold: parseFloat(String(a.threshold).match(/\d+/)?.[0] || '80'), ComparisonOperator: 'GreaterThanThreshold', Period: 300, EvaluationPeriods: 2 })) })
    }
    if (command === 'list-metrics') {
      const namespace = flags.namespace || 'AWS/EC2'
      const metricName = flags['metric-name']
      const seed = [
        ['AWS/EC2', 'CPUUtilization', 'InstanceId'],
        ['AWS/EC2', 'NetworkIn', 'InstanceId'],
        ['AWS/EC2', 'NetworkOut', 'InstanceId'],
        ['AWS/S3', 'BucketSizeBytes', 'BucketName'],
        ['AWS/Lambda', 'Invocations', 'FunctionName'],
        ['AWS/RDS', 'CPUUtilization', 'DBInstanceIdentifier'],
      ]
      return j({ Metrics: seed.filter(([ns, name]) => ns === namespace && (!metricName || name === metricName)).map(([Namespace, MetricName, dim]) => ({ Namespace, MetricName, Dimensions: [{ Name: dim, Value: 'demo' }] })) })
    }
    if (command === 'get-metric-statistics') {
      const now = Date.now()
      return j({ Label: flags['metric-name'] || 'CPUUtilization', Datapoints: Array.from({ length: 12 }, (_, i) => ({ Timestamp: new Date(now - (11 - i) * 300000).toISOString(), Average: Math.round((10 + Math.random() * 40) * 100) / 100, Unit: flags['metric-name']?.includes('Bytes') ? 'Bytes' : 'Percent' })) })
    }
    return `\nAn error occurred (InvalidAction) when calling the ${command} operation: aws cloudwatch ${command} is not yet simulated.`
  }

  // --- Generic AWS services backed by the console store ---
  // This covers the broad service catalog (Lambda, RDS, DynamoDB, ECS/EKS,
  // SQS/SNS, CloudFormation, Glue, Kinesis, etc.) so CloudShell and Terraform
  // can interact with the same resources rendered by the console pages.
  const serviceKey = GENERIC_SERVICE_ALIASES[service]
  const serviceCfg = SERVICE_CONFIGS[serviceKey]
  if (serviceCfg) {
    const commandSpecs = GENERIC_COMMANDS[serviceKey] || {}
    const resourceEntry = Object.entries(commandSpecs).find(([, spec]) => [spec.list, spec.describe, spec.create, spec.delete, spec.action].includes(command))
      || Object.entries(serviceCfg.resources).find(([resourceKey]) => command === `list-${resourceKey}` || command === `describe-${resourceKey}` || command === `create-${resourceKey}` || command === `delete-${resourceKey}`)

    if (resourceEntry) {
      const [resourceKey, specMaybe] = resourceEntry
      const spec = specMaybe.list ? specMaybe : { list: `list-${resourceKey}`, describe: `describe-${resourceKey}`, create: `create-${resourceKey}`, delete: `delete-${resourceKey}`, nameFlag: 'name', response: resourceKey }
      const cfg = serviceCfg.resources[resourceKey]
      const rows = (store.genericResources?.[serviceKey]?.[resourceKey] || []).filter((r) => !r.region || r.region === region)
      const name = pickResourceName(flags, spec)

      if (command === spec.list) {
        if (serviceKey === 'dynamodb') return j({ TableNames: rows.map((r) => r.name) })
        if (serviceKey === 'sqs') return j({ QueueUrls: rows.map((r) => `https://sqs.${region}.amazonaws.com/${ACCOUNT}/${r.name}`) })
        if (serviceKey === 'eks') return j({ clusters: rows.map((r) => r.name) })
        if (serviceKey === 'ecs') return j({ [spec.response || resourceKey]: rows.map((r) => genericResourceArn(serviceKey, resourceKey, r, region, cfg)) })
        if (serviceKey === 'glue' && resourceKey === 'jobs') return j({ JobNames: rows.map((r) => r.name) })
        if (serviceKey === 'kinesis') return j({ StreamNames: rows.map((r) => r.name), HasMoreStreams: false })
        return j({ [spec.response || resourceKey]: rows.map((r) => rowToGenericCli(serviceKey, resourceKey, r, region, cfg)) })
      }

      if (command === spec.describe) {
        const found = rows.find((r) => r.name === name || r.id === name || genericResourceArn(serviceKey, resourceKey, r, region, cfg) === name)
        // A named describe that matches nothing must fail — do NOT silently fall
        // back to the first row (which masked typos / deleted resources).
        if (name && !found) return `\nAn error occurred (ResourceNotFoundException) when calling the ${command} operation: ${serviceCfg.title} resource '${name}' not found`
        const row = found || rows[0]
        if (!row) return `\nAn error occurred (ResourceNotFoundException) when calling the ${command} operation: ${serviceCfg.title} resource not found`
        const body = rowToGenericCli(serviceKey, resourceKey, row, region, cfg)
        if (serviceKey === 'lambda') return j({ Configuration: { FunctionName: row.name, FunctionArn: body.Arn, Runtime: row.runtime, Handler: row.handler, MemorySize: row.memory, Timeout: row.timeout, State: row.status }, Code: { RepositoryType: 'S3', Location: 'https://awssim.local/lambda.zip' } })
        if (serviceKey === 'rds') return j({ DBInstances: [{ DBInstanceIdentifier: row.name, DBInstanceClass: row.class, Engine: row.engine, DBInstanceStatus: row.status, Endpoint: { Address: String(row.endpoint || '').split(':')[0], Port: Number(String(row.endpoint || '5432').split(':')[1] || 5432) }, AllocatedStorage: row.storage, DBInstanceArn: body.Arn }] })
        if (serviceKey === 'dynamodb') return j({ Table: { TableName: row.name, TableArn: body.Arn, TableStatus: row.status, ItemCount: row.items || 0, KeySchema: [{ AttributeName: 'pk', KeyType: 'HASH' }] } })
        if (serviceKey === 'eks') return j({ cluster: { name: row.name, arn: body.Arn, status: row.status, version: row.version, endpoint: `https://${row.name}.${region}.eks.amazonaws.com`, platformVersion: 'eks.6' } })
        return j({ [resourceKey.replace(/-/g, '_')]: body })
      }

      if (command === spec.create) {
        const denied = iamDeny(store, `${serviceKey}:${pascalCommand(command)}`, undefined, command)
        if (denied) return denied
        const createName = name || flags['queue-name'] || flags['topic-name'] || flags.name
        if (!createName) return `\nAn error occurred (ValidationException) when calling the ${command} operation: Missing required name parameter`
        const created = store.createGenericResource(serviceKey, resourceKey, { name: createName, ...knownCreateFlags(serviceKey, resourceKey, flags) })
        if (created && created.ok === false) return `\n${created.error}`
        const body = rowToGenericCli(serviceKey, resourceKey, created, region, cfg)
        if (serviceKey === 'sqs') return j({ QueueUrl: `https://sqs.${region}.amazonaws.com/${ACCOUNT}/${created.name}` })
        if (serviceKey === 'sns') return j({ TopicArn: body.Arn })
        if (serviceKey === 'lambda') return j({ FunctionName: created.name, FunctionArn: body.Arn, Runtime: created.runtime, State: created.status })
        if (serviceKey === 'dynamodb') return j({ TableDescription: { TableName: created.name, TableArn: body.Arn, TableStatus: created.status } })
        return j(body)
      }

      if (command === spec.delete) {
        const denied = iamDeny(store, `${serviceKey}:${pascalCommand(command)}`, undefined, command)
        if (denied) return denied
        const row = rows.find((r) => r.name === name || r.id === name || genericResourceArn(serviceKey, resourceKey, r, region, cfg) === name)
        if (!row) return `\nAn error occurred (ResourceNotFoundException) when calling the ${command} operation: ${serviceCfg.title} resource not found`
        store.deleteGenericResource(serviceKey, resourceKey, row.id)
        if (serviceKey === 'dynamodb') return j({ TableDescription: { TableName: row.name, TableStatus: 'DELETING' } })
        return ''
      }

      if (command === spec.action) {
        const denied = iamDeny(store, `${serviceKey}:${pascalCommand(command)}`, undefined, command)
        if (denied) return denied
        const found = rows.find((r) => r.name === name || r.id === name)
        // Same fix: a named action that matches nothing must fail explicitly.
        if (name && !found) return `\nAn error occurred (ResourceNotFoundException) when calling the ${command} operation: ${serviceCfg.title} resource '${name}' not found`
        const row = found || rows[0]
        if (!row) return `\nAn error occurred (ResourceNotFoundException) when calling the ${command} operation: ${serviceCfg.title} resource not found`
        store.updateGenericResource?.(serviceKey, resourceKey, row.id, { lastRun: new Date().toISOString(), status: row.status || 'Active' })
        return j({ [resourceKey.replace(/-/g, '_')]: rowToGenericCli(serviceKey, resourceKey, row, region, cfg) })
      }
    }
  }

  if (service === 'lambda' && command === 'list-functions') {
    const rows = (store.genericResources?.lambda?.functions || []).filter((r) => !r.region || r.region === region)
    return j({ Functions: rows.map((f) => ({ FunctionName: f.name, FunctionArn: arn('lambda', region, ACCOUNT, `function:${f.name}`), Runtime: f.runtime, Role: arn('iam', region, ACCOUNT, 'role/LambdaExecutionRole'), Handler: f.handler, CodeSize: 1024, Description: f.desc || '', Timeout: f.timeout, MemorySize: f.memory, LastModified: f.created, State: f.status })) })
  }

  if (service === 'rds' && command === 'describe-db-instances') {
    const rows = (store.genericResources?.rds?.databases || []).filter((r) => !r.region || r.region === region)
    return j({ DBInstances: rows.map((db) => ({ DBInstanceIdentifier: db.name, DBInstanceClass: db.class, Engine: db.engine, DBInstanceStatus: db.status, Endpoint: { Address: String(db.endpoint || '').split(':')[0], Port: Number(String(db.endpoint || '5432').split(':')[1] || 5432) }, AllocatedStorage: db.storage, DBInstanceArn: arn('rds', region, ACCOUNT, `db:${db.name}`) })) })
  }

  if (service === 'dynamodb' && command === 'list-tables') {
    const rows = (store.genericResources?.dynamodb?.tables || []).filter((r) => !r.region || r.region === region)
    return j({ TableNames: rows.map((t) => t.name) })
  }

  return `\nusage: aws [options] <command> <subcommand>\naws: error: argument command: Invalid choice or unsimulated service: '${service}'`
}
