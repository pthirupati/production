// AWS CLI simulation. Parses `aws <service> <command> [flags]` and returns
// realistic JSON/text output backed by the Zustand store. Supports a working
// subset that covers the seeded services; unknown commands return an AWS-style
// error so the terminal stays believable.
import { ACCOUNT } from '../store/awsStore'
import { arn } from '../lib/ids'

function parseFlags(tokens) {
  const flags = {}
  const positional = []
  for (let i = 0; i < tokens.length; i += 1) {
    const t = tokens[i]
    if (t.startsWith('--')) {
      const key = t.slice(2)
      const next = tokens[i + 1]
      if (next && !next.startsWith('--')) { flags[key] = next; i += 1 } else { flags[key] = true }
    } else positional.push(t)
  }
  return { flags, positional }
}

const j = (obj) => JSON.stringify(obj, null, 4)

export function awsCli(argv, store, ctx = {}) {
  const [service, command, ...rest] = argv
  const { flags } = parseFlags(rest)
  const region = flags.region || ctx.region || store.region

  if (!service || service === 'help') {
    return 'usage: aws [options] <command> <subcommand> [parameters]\nTo see help text, you can run:\n  aws help\n  aws <command> help'
  }

  // --- STS ---
  if (service === 'sts' && command === 'get-caller-identity') {
    return j({ UserId: `AIDAEXAMPLEUSERID`, Account: ACCOUNT, Arn: arn('iam', region, ACCOUNT, 'user/cli-user') })
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
    if (command === 'describe-instances') {
      const reservations = instances.map((i) => ({
        Groups: [],
        Instances: [{
          InstanceId: i.id, InstanceType: i.type, State: { Code: 16, Name: i.state },
          PrivateIpAddress: i.privateIp, PublicIpAddress: i.publicIp || undefined,
          ImageId: i.amiId, KeyName: i.keyName, LaunchTime: i.launchTime,
          Placement: { AvailabilityZone: i.az, Tenancy: i.tenancy },
          SubnetId: i.subnetId, VpcId: i.vpcId, Architecture: i.architecture,
          SecurityGroups: i.securityGroups.map((g) => ({ GroupId: g })),
          Tags: Object.entries(i.tags).map(([Key, Value]) => ({ Key, Value })),
        }],
        OwnerId: ACCOUNT, ReservationId: `r-0${Math.random().toString(16).slice(2, 18)}`,
      }))
      return j({ Reservations: reservations })
    }
    if (['start-instances', 'stop-instances', 'reboot-instances', 'terminate-instances'].includes(command)) {
      const ids = (flags['instance-ids'] || '').toString().split(/\s+/).filter(Boolean)
      const action = command.replace('-instances', '')
      store.instanceAction(ids, action)
      const key = { start: 'StartingInstances', stop: 'StoppingInstances', reboot: null, terminate: 'TerminatingInstances' }[action]
      if (action === 'reboot') return ''
      return j({ [key]: ids.map((id) => ({ InstanceId: id, CurrentState: { Name: action === 'start' ? 'pending' : action === 'stop' ? 'stopping' : 'shutting-down' }, PreviousState: { Name: 'running' } })) })
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
        Key: o.key, LastModified: o.modified, ETag: `"${Math.random().toString(16).slice(2, 34).padEnd(32, '0')}"`, Size: o.size, StorageClass: o.storageClass || 'STANDARD',
      }))
      return j({ Contents: contents, Name: bucket.name, Prefix: prefix, KeyCount: contents.length, MaxKeys: 1000, IsTruncated: false })
    }
    if (command === 'put-object') {
      if (!flags.bucket || !flags.key) return '\nAn error occurred (ValidationError) when calling the PutObject operation: Missing required bucket/key'
      store.putObject(flags.bucket, flags.key, flags.body ? 1024 : 0)
      return j({ ETag: `"${Math.random().toString(16).slice(2, 34).padEnd(32, '0')}"`, ServerSideEncryption: 'AES256' })
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
