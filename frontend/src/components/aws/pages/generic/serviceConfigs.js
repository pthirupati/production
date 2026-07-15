export const SERVICE_CONFIGS = {
  lambda: {
    title: 'Lambda',
    category: 'Compute',
    desc: 'Run code without provisioning or managing servers',
    primary: 'functions',
    resources: {
      functions: {
        label: 'Functions',
        createLabel: 'Create function',
        idLabel: 'Function name',
        arnService: 'lambda',
        arnResource: (r) => `function:${r.name}`,
        fields: [
          { key: 'name', label: 'Function name', input: 'text', required: true, group: 'Basic information' },
          { key: 'runtime', label: 'Runtime', input: 'select', group: 'Basic information', options: ['Python 3.12', 'Python 3.11', 'Node.js 20.x', 'Node.js 18.x', 'Java 21', 'Go 1.x', 'Ruby 3.3', '.NET 8'] },
          { key: 'handler', label: 'Handler', input: 'text', group: 'Runtime settings' },
          { key: 'memory', label: 'Memory', suffix: ' MB', input: 'number', min: 128, max: 10240, group: 'Configuration' },
          { key: 'timeout', label: 'Timeout', suffix: ' sec', input: 'number', min: 1, max: 900, group: 'Configuration' },
          { key: 'status', label: 'State', badge: true },
        ],
        defaults: { runtime: 'Python 3.12', memory: 128, timeout: 30, status: 'Pending', handler: 'lambda_function.lambda_handler', code: 'def lambda_handler(event, context):\n    return {"statusCode": 200, "body": "Hello from Lambda!"}', env: {}, triggers: [], invocationHistory: [] },
        lifecycle: { createStates: ['Pending', 'Active'], createDelayMs: 4000, deleteState: 'Inactive' },
        metrics: [
          { title: 'Invocations', unit: 'count', color: '#0073bb', base: 120, variance: 60 },
          { title: 'Duration', unit: 'ms', color: '#1d8102', base: 240, variance: 120 },
          { title: 'Errors', unit: 'count', color: '#d13212', base: 0, variance: 2 },
          { title: 'Throttles', unit: 'count', color: '#ff9900', base: 0, variance: 1 },
        ],
        tabs: ['Code', 'Configuration', 'Monitor', 'Aliases'],
        validate: (name, draft) => {
          if (!name || !/^[a-zA-Z0-9-_]{1,64}$/.test(name)) return 'Function name must be 1-64 chars, letters/numbers/hyphens/underscores only.'
          const mem = Number(draft.memory)
          if (draft.memory != null && (Number.isNaN(mem) || mem < 128 || mem > 10240)) return 'Memory must be between 128 and 10240 MB.'
          return ''
        },
      },
      layers: { label: 'Layers', createLabel: 'Create layer', idLabel: 'Layer name', arnService: 'lambda', arnResource: (r) => `layer:${r.name}`, fields: [{ key: 'name', label: 'Layer name' }, { key: 'runtime', label: 'Compatible runtime' }, { key: 'version', label: 'Latest version' }], defaults: { runtime: 'Python 3.12', version: 1, status: 'Active' } },
    },
  },
  rds: {
    title: 'RDS',
    category: 'Database',
    desc: 'Managed relational database service',
    primary: 'databases',
    resources: {
      databases: {
        label: 'Databases',
        createLabel: 'Create database',
        idLabel: 'DB identifier',
        arnService: 'rds',
        arnResource: (r) => `db:${r.name}`,
        fields: [
          { key: 'name', label: 'DB identifier', input: 'text', required: true, group: 'Settings' },
          { key: 'engine', label: 'Engine', input: 'select', group: 'Engine options', options: ['PostgreSQL 15.4', 'PostgreSQL 16.1', 'MySQL 8.0.35', 'MariaDB 10.11', 'Aurora PostgreSQL', 'Aurora MySQL', 'Oracle 19c', 'SQL Server 2022'] },
          { key: 'class', label: 'Class', input: 'select', group: 'Instance configuration', options: ['db.t3.micro', 'db.t3.small', 'db.t3.medium', 'db.m5.large', 'db.m5.xlarge', 'db.r5.large', 'db.r5.xlarge'] },
          { key: 'storage', label: 'Storage', suffix: ' GiB', input: 'number', min: 20, max: 65536, group: 'Storage' },
          { key: 'multiAz', label: 'Multi-AZ deployment', input: 'toggle', group: 'Availability & durability' },
          { key: 'status', label: 'Status', badge: true },
        ],
        defaults: { engine: 'PostgreSQL 15.4', class: 'db.t3.micro', storage: 20, multiAz: false, status: 'creating', endpoint: 'simulated.cluster.us-east-1.rds.amazonaws.com:5432' },
        lifecycle: {
          createStates: ['creating', 'backing-up', 'available'],
          createDelayMs: 5000,
          actions: {
            reboot: { interim: 'rebooting', final: 'available', delayMs: 6000 },
            modify: { interim: 'modifying', final: 'available', delayMs: 6000 },
            stop: { interim: 'stopping', final: 'stopped', delayMs: 6000 },
            start: { interim: 'starting', final: 'available', delayMs: 6000 },
          },
          deleteState: 'deleting',
        },
        metrics: [
          { title: 'CPUUtilization', unit: '%', color: '#0073bb', base: 18, variance: 22 },
          { title: 'DatabaseConnections', unit: 'count', color: '#1d8102', base: 12, variance: 8 },
          { title: 'FreeableMemory', unit: 'MB', color: '#ff9900', base: 780, variance: 120 },
          { title: 'ReadIOPS', unit: 'count/s', color: '#8b5cf6', base: 40, variance: 30 },
        ],
        tabs: ['Connectivity & security', 'Monitoring', 'Logs & events', 'Configuration', 'Maintenance & backups'],
        validate: (name, draft) => {
          if (!name || !/^[a-z][a-z0-9-]{0,62}$/.test(name)) return 'DB identifier must start with a letter and contain only lowercase letters, numbers, and hyphens.'
          const st = Number(draft.storage)
          if (draft.storage != null && (Number.isNaN(st) || st < 20 || st > 65536)) return 'Allocated storage must be between 20 and 65536 GiB.'
          return ''
        },
        derive: (name) => ({ endpoint: `${name}.c9akciq32xze.us-east-1.rds.amazonaws.com:5432` }),
      },
      snapshots: { label: 'Snapshots', createLabel: 'Create snapshot', idLabel: 'Snapshot name', arnService: 'rds', arnResource: (r) => `snapshot:${r.name}`, fields: [{ key: 'name', label: 'Snapshot' }, { key: 'engine', label: 'Engine' }, { key: 'status', label: 'Status', badge: true }, { key: 'created', label: 'Created' }], defaults: { engine: 'PostgreSQL', status: 'available' } },
    },
  },
  dynamodb: {
    title: 'DynamoDB',
    category: 'Database',
    desc: 'Fast and flexible NoSQL database service',
    primary: 'tables',
    resources: {
      tables: {
        label: 'Tables',
        createLabel: 'Create table',
        idLabel: 'Table name',
        arnService: 'dynamodb',
        arnResource: (r) => `table/${r.name}`,
        fields: [
          { key: 'name', label: 'Table name', input: 'text', required: true, group: 'Table details' },
          { key: 'partitionKey', label: 'Partition key', input: 'text', group: 'Table details' },
          { key: 'sortKey', label: 'Sort key', input: 'text', group: 'Table details' },
          { key: 'billingMode', label: 'Billing mode', input: 'radio-cards', group: 'Table settings', options: ['On-demand', 'Provisioned'] },
          { key: 'status', label: 'Status', badge: true },
          { key: 'items', label: 'Items' },
        ],
        defaults: { partitionKey: 'pk (String)', sortKey: 'sk (String)', billingMode: 'On-demand', status: 'CREATING', items: 0, records: [] },
        lifecycle: { createStates: ['CREATING', 'ACTIVE'], createDelayMs: 4000, deleteState: 'DELETING' },
        metrics: [
          { title: 'ConsumedReadCapacityUnits', unit: 'count', color: '#0073bb', base: 30, variance: 20 },
          { title: 'ConsumedWriteCapacityUnits', unit: 'count', color: '#1d8102', base: 18, variance: 12 },
          { title: 'ThrottledRequests', unit: 'count', color: '#d13212', base: 0, variance: 1 },
        ],
        tabs: ['Overview', 'Indexes', 'Monitor', 'Explore table items'],
        validate: (name) => {
          if (!name || !/^[a-zA-Z0-9._-]{3,255}$/.test(name)) return 'Table name must be 3-255 chars: letters, numbers, dot, dash, underscore.'
          return ''
        },
      },
    },
  },
  cloudformation: {
    title: 'CloudFormation',
    category: 'Management & Governance',
    desc: 'Model and provision AWS resources with templates',
    primary: 'stacks',
    resources: {
      stacks: {
        label: 'Stacks',
        createLabel: 'Create stack',
        idLabel: 'Stack name',
        arnService: 'cloudformation',
        arnResource: (r) => `stack/${r.name}/${r.id}`,
        fields: [
          { key: 'name', label: 'Stack name', input: 'text', required: true, group: 'Specify stack details' },
          { key: 'status', label: 'Status', badge: true },
          { key: 'resources', label: 'Resources' },
          { key: 'created', label: 'Created' },
        ],
        defaults: { status: 'CREATE_IN_PROGRESS', resources: 0, events: [], outputs: [], resourceList: [] },
        lifecycle: { createStates: ['CREATE_IN_PROGRESS', 'CREATE_COMPLETE'], createDelayMs: 5000, deleteState: 'DELETE_IN_PROGRESS' },
        tabs: ['Stack info', 'Events', 'Resources', 'Outputs', 'Parameters', 'Template'],
        validate: (name) => {
          if (!name || !/^[a-zA-Z][a-zA-Z0-9-]{0,127}$/.test(name)) return 'Stack name must start with a letter and contain only letters, numbers, and hyphens.'
          return ''
        },
      },
      'change-sets': { label: 'Change sets', createLabel: 'Create change set', idLabel: 'Change set name', arnService: 'cloudformation', arnResource: (r) => `changeSet/${r.name}/${r.id}`, fields: [{ key: 'name', label: 'Change set' }, { key: 'status', label: 'Status', badge: true }, { key: 'changes', label: 'Changes' }], defaults: { status: 'CREATE_COMPLETE', changes: 2 } },
    },
  },
  route53: {
    title: 'Route 53',
    category: 'Networking & Content Delivery',
    desc: 'Highly available and scalable DNS',
    primary: 'hosted-zones',
    resources: {
      'hosted-zones': { label: 'Hosted zones', createLabel: 'Create hosted zone', idLabel: 'Domain name', arnService: 'route53', arnResource: (r) => `hostedzone/${r.id}`, fields: [{ key: 'name', label: 'Domain name' }, { key: 'type', label: 'Type' }, { key: 'records', label: 'Record count' }, { key: 'status', label: 'Status', badge: true }], defaults: { type: 'Public', records: 5, status: 'available' } },
      'health-checks': { label: 'Health checks', createLabel: 'Create health check', idLabel: 'Health check name', arnService: 'route53', arnResource: (r) => `healthcheck/${r.id}`, fields: [{ key: 'name', label: 'Name' }, { key: 'protocol', label: 'Protocol' }, { key: 'status', label: 'Status', badge: true }], defaults: { protocol: 'HTTPS', status: 'Healthy' } },
    },
  },
  sns: {
    title: 'SNS',
    category: 'Application Integration',
    desc: 'Pub/sub messaging and mobile notifications',
    primary: 'topics',
    resources: {
      topics: {
        label: 'Topics',
        createLabel: 'Create topic',
        idLabel: 'Topic name',
        arnService: 'sns',
        arnResource: (r) => r.name,
        fields: [
          { key: 'name', label: 'Topic name', input: 'text', required: true, group: 'Details' },
          { key: 'type', label: 'Type', input: 'radio-cards', group: 'Details', options: ['Standard', 'FIFO'] },
          { key: 'subscriptions', label: 'Subscriptions', input: 'number', min: 0, max: 10000, group: 'Access policy' },
          { key: 'status', label: 'Status', badge: true },
        ],
        defaults: { type: 'Standard', subscriptions: 1, status: 'Active' },
        metrics: [
          { title: 'NumberOfMessagesPublished', unit: 'count', color: '#0073bb', base: 60, variance: 40 },
          { title: 'NumberOfNotificationsDelivered', unit: 'count', color: '#1d8102', base: 58, variance: 38 },
          { title: 'NumberOfNotificationsFailed', unit: 'count', color: '#d13212', base: 0, variance: 2 },
        ],
        validate: (name, draft) => {
          if (!name || !/^[a-zA-Z0-9_-]{1,256}$/.test(name)) return 'Topic name must be 1-256 chars: letters, numbers, hyphens, underscores.'
          if (draft.type === 'FIFO' && !name.endsWith('.fifo')) return 'FIFO topic names must end with the .fifo suffix.'
          if (draft.type !== 'FIFO' && name.endsWith('.fifo')) return 'The .fifo suffix is only allowed for FIFO topics.'
          return ''
        },
      },
      subscriptions: {
        label: 'Subscriptions',
        createLabel: 'Create subscription',
        idLabel: 'Endpoint',
        arnService: 'sns',
        arnResource: (r) => r.id,
        fields: [
          { key: 'name', label: 'Endpoint', input: 'text', required: true, group: 'Details' },
          { key: 'protocol', label: 'Protocol', input: 'select', group: 'Details', options: ['Email', 'Email-JSON', 'SMS', 'HTTPS', 'HTTP', 'Lambda', 'SQS', 'Application'] },
          { key: 'status', label: 'Status', badge: true },
        ],
        defaults: { protocol: 'Email', status: 'Confirmed' },
      },
    },
  },
  sqs: {
    title: 'SQS',
    category: 'Application Integration',
    desc: 'Managed message queues',
    primary: 'queues',
    resources: {
      queues: {
        label: 'Queues',
        createLabel: 'Create queue',
        idLabel: 'Queue name',
        arnService: 'sqs',
        arnResource: (r) => r.name,
        fields: [
          { key: 'name', label: 'Queue name', input: 'text', required: true, group: 'Details' },
          { key: 'type', label: 'Type', input: 'radio-cards', group: 'Details', options: ['Standard', 'FIFO'] },
          { key: 'visibilityTimeout', label: 'Visibility timeout', suffix: ' sec', input: 'number', min: 0, max: 43200, group: 'Configuration' },
          { key: 'messages', label: 'Available messages' },
          { key: 'status', label: 'Status', badge: true },
        ],
        defaults: { type: 'Standard', visibilityTimeout: 30, messages: 0, status: 'Active' },
        metrics: [
          { title: 'NumberOfMessagesSent', unit: 'count', color: '#0073bb', base: 40, variance: 30 },
          { title: 'NumberOfMessagesReceived', unit: 'count', color: '#1d8102', base: 38, variance: 28 },
          { title: 'ApproximateNumberOfMessagesVisible', unit: 'count', color: '#ff9900', base: 4, variance: 12 },
          { title: 'ApproximateAgeOfOldestMessage', unit: 's', color: '#8b5cf6', base: 2, variance: 30 },
        ],
        validate: (name, draft) => {
          if (draft.type === 'FIFO') {
            if (!name || !/^[a-zA-Z0-9_-]{1,75}\.fifo$/.test(name)) return 'FIFO queue names must be 1-80 chars and end with the .fifo suffix.'
          } else if (!name || !/^[a-zA-Z0-9_-]{1,80}$/.test(name)) {
            return 'Queue name must be 1-80 chars: letters, numbers, hyphens, underscores.'
          } else if (name.endsWith('.fifo')) {
            return 'The .fifo suffix is only allowed for FIFO queues.'
          }
          return ''
        },
      },
    },
  },
  secretsmanager: {
    title: 'Secrets Manager',
    category: 'Security, Identity & Compliance',
    desc: 'Protect secrets needed to access applications and services',
    primary: 'secrets',
    resources: {
      secrets: { label: 'Secrets', createLabel: 'Store a new secret', idLabel: 'Secret name', arnService: 'secretsmanager', arnResource: (r) => `secret:${r.name}-${r.id.slice(-6)}`, fields: [{ key: 'name', label: 'Secret name' }, { key: 'rotation', label: 'Rotation' }, { key: 'lastChanged', label: 'Last changed' }, { key: 'status', label: 'Status', badge: true }], defaults: { rotation: 'Disabled', lastChanged: 'Today', status: 'Active' } },
    },
  },
  acm: {
    title: 'Certificate Manager',
    category: 'Security, Identity & Compliance',
    desc: 'Provision, manage, and deploy SSL/TLS certificates',
    primary: 'certificates',
    resources: {
      certificates: { label: 'Certificates', createLabel: 'Request certificate', idLabel: 'Domain name', arnService: 'acm', arnResource: (r) => `certificate/${r.id}`, fields: [{ key: 'name', label: 'Domain name' }, { key: 'type', label: 'Type' }, { key: 'status', label: 'Status', badge: true }, { key: 'expires', label: 'Expires' }], defaults: { type: 'Amazon issued', status: 'Issued', expires: '2027-03-01' } },
    },
  },
  cloudfront: {
    title: 'CloudFront',
    category: 'Networking & Content Delivery',
    desc: 'Global content delivery network',
    primary: 'distributions',
    resources: {
      distributions: {
        label: 'Distributions',
        createLabel: 'Create distribution',
        idLabel: 'Distribution name',
        arnService: 'cloudfront',
        arnResource: (r) => `distribution/${r.id}`,
        fields: [
          { key: 'name', label: 'Distribution', input: 'text', required: true, group: 'Origin' },
          { key: 'priceClass', label: 'Price class', input: 'select', group: 'Settings', options: ['Use all edge locations', 'Use only North America and Europe', 'Use North America, Europe, Asia, Middle East, and Africa'] },
          { key: 'domainName', label: 'Domain name' },
          { key: 'status', label: 'Status', badge: true },
        ],
        defaults: { domainName: 'd111111abcdef8.cloudfront.net', status: 'Deployed', priceClass: 'Use all edge locations' },
        metrics: [
          { title: 'Requests', unit: 'count', color: '#0073bb', base: 800, variance: 1200 },
          { title: 'BytesDownloaded', unit: 'MB', color: '#1d8102', base: 300, variance: 400 },
          { title: 'TotalErrorRate', unit: '%', color: '#d13212', base: 0, variance: 3 },
          { title: 'CacheHitRate', unit: '%', color: '#8b5cf6', base: 88, variance: 10 },
        ],
      },
    },
  },
  eks: {
    title: 'EKS',
    category: 'Containers',
    desc: 'Managed Kubernetes service',
    primary: 'clusters',
    resources: {
      clusters: {
        label: 'Clusters',
        createLabel: 'Create cluster',
        idLabel: 'Cluster name',
        arnService: 'eks',
        arnResource: (r) => `cluster/${r.name}`,
        fields: [
          { key: 'name', label: 'Name', input: 'text', required: true, group: 'Configure cluster' },
          { key: 'version', label: 'Kubernetes version', input: 'select', group: 'Configure cluster', options: ['1.30', '1.29', '1.28', '1.27'] },
          { key: 'nodes', label: 'Nodes', input: 'number', min: 0, max: 100, group: 'Compute' },
          { key: 'status', label: 'Status', badge: true },
        ],
        defaults: { version: '1.30', nodes: 3, status: 'CREATING' },
        lifecycle: { createStates: ['CREATING', 'ACTIVE'], createDelayMs: 6000, deleteState: 'DELETING' },
        metrics: [
          { title: 'cluster_node_count', unit: 'count', color: '#0073bb', base: 3, variance: 4 },
          { title: 'cluster_failed_node_count', unit: 'count', color: '#d13212', base: 0, variance: 1 },
          { title: 'apiserver_request_total', unit: 'count', color: '#1d8102', base: 120, variance: 90 },
          { title: 'apiserver_request_duration', unit: 'ms', color: '#9d5025', base: 18, variance: 40 },
        ],
        tabs: ['Overview', 'Resources', 'Compute', 'Networking', 'Add-ons'],
        validate: (name) => {
          if (!name || !/^[a-zA-Z0-9][a-zA-Z0-9-_]{0,99}$/.test(name)) return 'Cluster name must start alphanumeric, 1-100 chars: letters, numbers, hyphen, underscore.'
          return ''
        },
      },
      'node-groups': {
        label: 'Node groups',
        createLabel: 'Create node group',
        idLabel: 'Node group name',
        arnService: 'eks',
        arnResource: (r) => `nodegroup/demo/${r.name}/${r.id}`,
        fields: [
          { key: 'name', label: 'Name', input: 'text', required: true, group: 'Node group configuration' },
          { key: 'instanceType', label: 'Instance type', input: 'select', group: 'Compute', options: ['t3.medium', 't3.large', 't3.xlarge', 'm5.large', 'm5.xlarge', 'c5.large', 'r5.large'] },
          { key: 'capacityType', label: 'Capacity type', input: 'radio-cards', group: 'Compute', options: ['On-Demand', 'Spot'] },
          { key: 'desired', label: 'Desired size', input: 'number', min: 0, max: 100, group: 'Node group scaling' },
          { key: 'status', label: 'Status', badge: true },
        ],
        defaults: { instanceType: 't3.medium', capacityType: 'On-Demand', desired: 3, status: 'Active' },
        metrics: [
          { title: 'node_cpu_utilization', unit: '%', color: '#0073bb', base: 22, variance: 30 },
          { title: 'node_memory_utilization', unit: '%', color: '#1d8102', base: 40, variance: 25 },
          { title: 'pod_number_of_running_pods', unit: 'count', color: '#8b5cf6', base: 12, variance: 8 },
        ],
      },
    },
  },
  ecs: {
    title: 'ECS',
    category: 'Containers',
    desc: 'Run and manage containers',
    primary: 'clusters',
    resources: {
      clusters: {
        label: 'Clusters',
        createLabel: 'Create cluster',
        idLabel: 'Cluster name',
        arnService: 'ecs',
        arnResource: (r) => `cluster/${r.name}`,
        fields: [
          { key: 'name', label: 'Cluster', input: 'text', required: true, group: 'Cluster configuration' },
          { key: 'provider', label: 'Infrastructure', input: 'radio-cards', group: 'Infrastructure', options: ['AWS Fargate', 'Amazon EC2', 'External'] },
          { key: 'services', label: 'Services' },
          { key: 'tasks', label: 'Running tasks' },
          { key: 'status', label: 'Status', badge: true },
        ],
        defaults: { provider: 'AWS Fargate', services: 1, tasks: 2, status: 'Active' },
        metrics: [
          { title: 'CPUUtilization', unit: '%', color: '#0073bb', base: 24, variance: 30 },
          { title: 'MemoryUtilization', unit: '%', color: '#1d8102', base: 38, variance: 25 },
          { title: 'RunningTaskCount', unit: 'count', color: '#8b5cf6', base: 2, variance: 4 },
        ],
      },
      services: {
        label: 'Services',
        createLabel: 'Create service',
        idLabel: 'Service name',
        arnService: 'ecs',
        arnResource: (r) => `service/default/${r.name}`,
        fields: [
          { key: 'name', label: 'Service', input: 'text', required: true, group: 'Service details' },
          { key: 'launchType', label: 'Launch type', input: 'radio-cards', group: 'Compute configuration', options: ['FARGATE', 'EC2', 'EXTERNAL'] },
          { key: 'desired', label: 'Desired', input: 'number', min: 0, max: 1000, group: 'Service details' },
          { key: 'running', label: 'Running' },
          { key: 'status', label: 'Status', badge: true },
        ],
        defaults: { launchType: 'FARGATE', desired: 2, running: 2, status: 'Active' },
        metrics: [
          { title: 'CPUUtilization', unit: '%', color: '#0073bb', base: 26, variance: 30 },
          { title: 'MemoryUtilization', unit: '%', color: '#1d8102', base: 42, variance: 25 },
        ],
      },
      tasks: {
        label: 'Tasks',
        createLabel: 'Run task',
        idLabel: 'Task family',
        arnService: 'ecs',
        arnResource: (r) => `task/default/${r.id}`,
        fields: [
          { key: 'name', label: 'Task', input: 'text', required: true, group: 'Task configuration' },
          { key: 'launchType', label: 'Launch type', input: 'radio-cards', group: 'Compute configuration', options: ['FARGATE', 'EC2', 'EXTERNAL'] },
          { key: 'count', label: 'Desired tasks', input: 'number', min: 1, max: 100, group: 'Task configuration' },
          { key: 'status', label: 'Status', badge: true },
        ],
        defaults: { launchType: 'FARGATE', count: 1, status: 'RUNNING' },
      },
    },
  },
  ecr: {
    title: 'ECR',
    category: 'Containers',
    desc: 'Container image registry',
    primary: 'repositories',
    resources: {
      repositories: {
        label: 'Repositories',
        createLabel: 'Create repository',
        idLabel: 'Repository name',
        arnService: 'ecr',
        arnResource: (r) => `repository/${r.name}`,
        fields: [
          { key: 'name', label: 'Repository name', input: 'text', required: true, group: 'General settings' },
          { key: 'visibility', label: 'Visibility', input: 'radio-cards', group: 'General settings', options: ['Private', 'Public'] },
          { key: 'tagMutability', label: 'Tag immutability', input: 'select', group: 'General settings', options: ['Mutable', 'Immutable'] },
          { key: 'scanOnPush', label: 'Scan on push', input: 'select', group: 'Image scan settings', options: ['Enabled', 'Disabled'] },
          { key: 'images', label: 'Images' },
          { key: 'status', label: 'Status', badge: true },
        ],
        defaults: { visibility: 'Private', tagMutability: 'Mutable', images: 3, scanOnPush: 'Enabled', status: 'Active' },
        metrics: [
          { title: 'RepositoryPullCount', unit: 'count', color: '#0073bb', base: 24, variance: 30 },
          { title: 'RepositoryPushCount', unit: 'count', color: '#1d8102', base: 6, variance: 10 },
          { title: 'ScanFindings', unit: 'count', color: '#d13212', base: 0, variance: 4 },
        ],
        validate: (name) => {
          if (!name || !/^[a-z0-9]+(?:[._/-][a-z0-9]+)*$/.test(name) || name.length > 256) return 'Repository name must be lowercase and may include hyphens, underscores, dots, and slashes.'
          return ''
        },
      },
    },
  },
  apigateway: {
    title: 'API Gateway',
    category: 'Networking & Content Delivery',
    desc: 'Create, publish, maintain, monitor, and secure APIs',
    primary: 'apis',
    resources: {
      apis: {
        label: 'APIs',
        createLabel: 'Create API',
        idLabel: 'API name',
        arnService: 'apigateway',
        arnResource: (r) => `/apis/${r.id}`,
        fields: [
          { key: 'name', label: 'API name', input: 'text', required: true, group: 'API details' },
          { key: 'type', label: 'Type', input: 'radio-cards', group: 'API details', options: ['HTTP', 'REST', 'WebSocket'] },
          { key: 'stage', label: 'Stage', input: 'text', group: 'Deployment' },
          { key: 'status', label: 'Status', badge: true },
        ],
        defaults: { type: 'HTTP', stage: 'prod', status: 'Active' },
        metrics: [
          { title: 'Count', unit: 'count', color: '#0073bb', base: 300, variance: 500 },
          { title: 'Latency', unit: 'ms', color: '#9d5025', base: 40, variance: 120 },
          { title: '4XXError', unit: 'count', color: '#ff9900', base: 2, variance: 10 },
          { title: '5XXError', unit: 'count', color: '#d13212', base: 0, variance: 4 },
        ],
      },
    },
  },
  eventbridge: {
    title: 'EventBridge',
    category: 'Application Integration',
    desc: 'Serverless event bus',
    primary: 'rules',
    resources: { rules: { label: 'Rules', createLabel: 'Create rule', idLabel: 'Rule name', arnService: 'events', arnResource: (r) => `rule/${r.name}`, fields: [{ key: 'name', label: 'Rule name' }, { key: 'eventBus', label: 'Event bus' }, { key: 'targets', label: 'Targets' }, { key: 'status', label: 'Status', badge: true }], defaults: { eventBus: 'default', targets: 1, status: 'Enabled' } } },
  },
  states: {
    title: 'Step Functions',
    category: 'Application Integration',
    desc: 'Coordinate distributed applications',
    primary: 'state-machines',
    resources: { 'state-machines': { label: 'State machines', createLabel: 'Create state machine', idLabel: 'State machine name', arnService: 'states', arnResource: (r) => `stateMachine:${r.name}`, fields: [{ key: 'name', label: 'Name' }, { key: 'type', label: 'Type' }, { key: 'executions', label: 'Executions' }, { key: 'status', label: 'Status', badge: true }], defaults: { type: 'STANDARD', executions: 12, status: 'Active' } } },
  },
  kms: {
    title: 'KMS',
    category: 'Security, Identity & Compliance',
    desc: 'Create and control cryptographic keys',
    primary: 'keys',
    resources: { keys: { label: 'Customer managed keys', createLabel: 'Create key', idLabel: 'Alias', arnService: 'kms', arnResource: (r) => `key/${r.id}`, fields: [{ key: 'name', label: 'Alias' }, { key: 'usage', label: 'Key usage' }, { key: 'rotation', label: 'Rotation' }, { key: 'status', label: 'Status', badge: true }], defaults: { usage: 'Encrypt and decrypt', rotation: 'Enabled', status: 'Enabled' } } },
  },
  cloudtrail: {
    title: 'CloudTrail',
    category: 'Management & Governance',
    desc: 'Track user activity and API usage',
    primary: 'trails',
    resources: { trails: { label: 'Trails', createLabel: 'Create trail', idLabel: 'Trail name', arnService: 'cloudtrail', arnResource: (r) => `trail/${r.name}`, fields: [{ key: 'name', label: 'Trail name' }, { key: 'multiRegion', label: 'Multi-region' }, { key: 'logging', label: 'Logging' }, { key: 'status', label: 'Status', badge: true }], defaults: { multiRegion: 'Yes', logging: 'On', status: 'Active' } } },
  },
  config: {
    title: 'AWS Config',
    category: 'Management & Governance',
    desc: 'Assess, audit, and evaluate resource configurations',
    primary: 'rules',
    resources: { rules: { label: 'Rules', createLabel: 'Add rule', idLabel: 'Rule name', arnService: 'config', arnResource: (r) => `config-rule/${r.id}`, fields: [{ key: 'name', label: 'Rule name' }, { key: 'compliance', label: 'Compliance' }, { key: 'evaluations', label: 'Evaluations' }, { key: 'status', label: 'Status', badge: true }], defaults: { compliance: 'COMPLIANT', evaluations: 24, status: 'Active' } } },
  },
  systemsmanager: {
    title: 'Systems Manager',
    category: 'Management & Governance',
    desc: 'View and control infrastructure at scale',
    primary: 'parameters',
    resources: { parameters: { label: 'Parameter Store', createLabel: 'Create parameter', idLabel: 'Parameter name', arnService: 'ssm', arnResource: (r) => `parameter/${r.name}`, fields: [{ key: 'name', label: 'Name' }, { key: 'type', label: 'Type' }, { key: 'tier', label: 'Tier' }, { key: 'status', label: 'Status', badge: true }], defaults: { type: 'String', tier: 'Standard', status: 'Active' } } },
  },
  billing: {
    title: 'Billing and Cost Management',
    category: 'Cloud Financial Management',
    desc: 'Track usage, cost, budgets, and forecasts',
    primary: 'budgets',
    resources: { budgets: { label: 'Budgets', createLabel: 'Create budget', idLabel: 'Budget name', arnService: 'budgets', arnResource: (r) => `budget/${r.name}`, fields: [{ key: 'name', label: 'Budget name' }, { key: 'amount', label: 'Amount', prefix: '$' }, { key: 'actual', label: 'Actual', prefix: '$' }, { key: 'status', label: 'Status', badge: true }], defaults: { amount: 100, actual: 47.32, status: 'OK' } } },
  },
  waf: {
    title: 'WAF & Shield',
    category: 'Security, Identity & Compliance',
    desc: 'Protect web applications from common exploits',
    primary: 'web-acls',
    resources: { 'web-acls': { label: 'Web ACLs', createLabel: 'Create web ACL', idLabel: 'Web ACL name', arnService: 'wafv2', arnResource: (r) => `regional/webacl/${r.name}/${r.id}`, fields: [{ key: 'name', label: 'Name' }, { key: 'scope', label: 'Scope' }, { key: 'rules', label: 'Rules' }, { key: 'status', label: 'Status', badge: true }], defaults: { scope: 'Regional', rules: 3, status: 'Active' } } },
  },
  cognito: {
    title: 'Cognito',
    category: 'Security, Identity & Compliance',
    desc: 'User identity and access for apps',
    primary: 'user-pools',
    resources: { 'user-pools': { label: 'User pools', createLabel: 'Create user pool', idLabel: 'User pool name', arnService: 'cognito-idp', arnResource: (r) => `userpool/${r.id}`, fields: [{ key: 'name', label: 'Pool name' }, { key: 'users', label: 'Users' }, { key: 'mfa', label: 'MFA' }, { key: 'status', label: 'Status', badge: true }], defaults: { users: 24, mfa: 'Optional', status: 'Enabled' } } },
  },
  elasticache: {
    title: 'ElastiCache',
    category: 'Database',
    desc: 'In-memory caching service',
    primary: 'clusters',
    resources: {
      clusters: {
        label: 'Clusters',
        createLabel: 'Create cluster',
        idLabel: 'Cluster name',
        arnService: 'elasticache',
        arnResource: (r) => `cluster:${r.name}`,
        fields: [
          { key: 'name', label: 'Cluster name', input: 'text', required: true, group: 'Cluster settings' },
          { key: 'engine', label: 'Engine', input: 'select', group: 'Cluster settings', options: ['Redis OSS', 'Valkey', 'Memcached'] },
          { key: 'nodeType', label: 'Node type', input: 'select', group: 'Cluster settings', options: ['cache.t3.micro', 'cache.t3.small', 'cache.t3.medium', 'cache.m6g.large', 'cache.r6g.large'] },
          { key: 'nodes', label: 'Nodes', input: 'number', min: 1, max: 40, group: 'Cluster settings' },
          { key: 'status', label: 'Status', badge: true },
        ],
        defaults: { engine: 'Redis OSS', nodeType: 'cache.t3.micro', nodes: 2, status: 'available' },
        metrics: [
          { title: 'CPUUtilization', unit: '%', color: '#0073bb', base: 16, variance: 24 },
          { title: 'DatabaseMemoryUsagePercentage', unit: '%', color: '#1d8102', base: 32, variance: 30 },
          { title: 'CacheHits', unit: 'count', color: '#8b5cf6', base: 400, variance: 300 },
          { title: 'CacheMisses', unit: 'count', color: '#d13212', base: 12, variance: 20 },
        ],
      },
    },
  },
  redshift: {
    title: 'Redshift',
    category: 'Analytics',
    desc: 'Cloud data warehouse',
    primary: 'clusters',
    resources: {
      clusters: {
        label: 'Clusters',
        createLabel: 'Create cluster',
        idLabel: 'Cluster name',
        arnService: 'redshift',
        arnResource: (r) => `cluster:${r.name}`,
        fields: [
          { key: 'name', label: 'Cluster name', input: 'text', required: true, group: 'Cluster configuration' },
          { key: 'nodeType', label: 'Node type', input: 'select', group: 'Cluster configuration', options: ['ra3.large', 'ra3.xlplus', 'ra3.4xlarge', 'ra3.16xlarge', 'dc2.large', 'dc2.8xlarge'] },
          { key: 'nodes', label: 'Nodes', input: 'number', min: 1, max: 128, group: 'Cluster configuration' },
          { key: 'status', label: 'Status', badge: true },
        ],
        defaults: { nodeType: 'ra3.xlplus', nodes: 2, status: 'available' },
        metrics: [
          { title: 'CPUUtilization', unit: '%', color: '#0073bb', base: 20, variance: 30 },
          { title: 'PercentageDiskSpaceUsed', unit: '%', color: '#1d8102', base: 28, variance: 20 },
          { title: 'DatabaseConnections', unit: 'count', color: '#8b5cf6', base: 6, variance: 10 },
        ],
      },
    },
  },
  opensearch: {
    title: 'OpenSearch Service',
    category: 'Analytics',
    desc: 'Search, visualize, and analyze text and logs',
    primary: 'domains',
    resources: { domains: { label: 'Domains', createLabel: 'Create domain', idLabel: 'Domain name', arnService: 'es', arnResource: (r) => `domain/${r.name}`, fields: [{ key: 'name', label: 'Domain name' }, { key: 'version', label: 'Version' }, { key: 'nodes', label: 'Nodes' }, { key: 'status', label: 'Status', badge: true }], defaults: { version: 'OpenSearch 2.13', nodes: 3, status: 'Active' } } },
  },
  kinesis: {
    title: 'Kinesis',
    category: 'Analytics',
    desc: 'Collect, process, and analyze streaming data',
    primary: 'streams',
    resources: {
      streams: {
        label: 'Data streams',
        createLabel: 'Create stream',
        idLabel: 'Stream name',
        arnService: 'kinesis',
        arnResource: (r) => `stream/${r.name}`,
        fields: [
          { key: 'name', label: 'Stream name', input: 'text', required: true, group: 'Data stream configuration' },
          { key: 'mode', label: 'Capacity mode', input: 'radio-cards', group: 'Data stream capacity', options: ['On-demand', 'Provisioned'] },
          { key: 'shards', label: 'Provisioned shards', input: 'number', min: 1, max: 500, group: 'Data stream capacity' },
          { key: 'status', label: 'Status', badge: true },
        ],
        defaults: { mode: 'On-demand', shards: 4, status: 'Active' },
        metrics: [
          { title: 'IncomingRecords', unit: 'count', color: '#0073bb', base: 200, variance: 300 },
          { title: 'IncomingBytes', unit: 'KB', color: '#1d8102', base: 120, variance: 200 },
          { title: 'GetRecords.IteratorAgeMilliseconds', unit: 'ms', color: '#9d5025', base: 40, variance: 120 },
          { title: 'WriteProvisionedThroughputExceeded', unit: 'count', color: '#d13212', base: 0, variance: 2 },
        ],
        validate: (name) => {
          if (!name || !/^[a-zA-Z0-9_.-]{1,128}$/.test(name)) return 'Stream name must be 1-128 chars: letters, numbers, dot, dash, underscore.'
          return ''
        },
      },
    },
  },
  glue: {
    title: 'Glue',
    category: 'Analytics',
    desc: 'Serverless data integration',
    primary: 'jobs',
    resources: { jobs: { label: 'ETL jobs', createLabel: 'Create job', idLabel: 'Job name', arnService: 'glue', arnResource: (r) => `job/${r.name}`, fields: [{ key: 'name', label: 'Job name' }, { key: 'type', label: 'Type' }, { key: 'runs', label: 'Runs' }, { key: 'status', label: 'Status', badge: true }], defaults: { type: 'Spark', runs: 8, status: 'Active' } }, databases: { label: 'Databases', createLabel: 'Create database', idLabel: 'Database name', arnService: 'glue', arnResource: (r) => `database/${r.name}`, fields: [{ key: 'name', label: 'Database' }, { key: 'tables', label: 'Tables' }, { key: 'status', label: 'Status', badge: true }], defaults: { tables: 6, status: 'Active' } } },
  },
  athena: {
    title: 'Athena',
    category: 'Analytics',
    desc: 'Query data in S3 using SQL',
    primary: 'workgroups',
    resources: { workgroups: { label: 'Workgroups', createLabel: 'Create workgroup', idLabel: 'Workgroup name', arnService: 'athena', arnResource: (r) => `workgroup/${r.name}`, fields: [{ key: 'name', label: 'Workgroup' }, { key: 'queries', label: 'Queries' }, { key: 'bytesScanned', label: 'Bytes scanned' }, { key: 'status', label: 'Status', badge: true }], defaults: { queries: 18, bytesScanned: '1.2 GB', status: 'Enabled' } } },
  },
  codecommit: {
    title: 'CodeCommit',
    category: 'Developer Tools',
    desc: 'Private Git repositories',
    primary: 'repositories',
    resources: { repositories: { label: 'Repositories', createLabel: 'Create repository', idLabel: 'Repository name', arnService: 'codecommit', arnResource: (r) => r.name, fields: [{ key: 'name', label: 'Repository' }, { key: 'defaultBranch', label: 'Default branch' }, { key: 'commits', label: 'Commits' }, { key: 'status', label: 'Status', badge: true }], defaults: { defaultBranch: 'main', commits: 42, status: 'Active' } } },
  },
  codebuild: {
    title: 'CodeBuild',
    category: 'Developer Tools',
    desc: 'Build and test code',
    primary: 'projects',
    resources: { projects: { label: 'Projects', createLabel: 'Create project', idLabel: 'Project name', arnService: 'codebuild', arnResource: (r) => `project/${r.name}`, fields: [{ key: 'name', label: 'Project' }, { key: 'environment', label: 'Environment' }, { key: 'lastBuild', label: 'Last build' }, { key: 'status', label: 'Status', badge: true }], defaults: { environment: 'Linux container', lastBuild: 'SUCCEEDED', status: 'Active' } } },
  },
  codepipeline: {
    title: 'CodePipeline',
    category: 'Developer Tools',
    desc: 'Continuous delivery pipelines',
    primary: 'pipelines',
    resources: { pipelines: { label: 'Pipelines', createLabel: 'Create pipeline', idLabel: 'Pipeline name', arnService: 'codepipeline', arnResource: (r) => r.name, fields: [{ key: 'name', label: 'Pipeline' }, { key: 'stages', label: 'Stages' }, { key: 'lastExecution', label: 'Last execution' }, { key: 'status', label: 'Status', badge: true }], defaults: { stages: 3, lastExecution: 'Succeeded', status: 'Active' } } },
  },
  organizations: {
    title: 'Organizations',
    category: 'Management & Governance',
    desc: 'Centrally manage AWS accounts',
    primary: 'accounts',
    resources: { accounts: { label: 'Accounts', createLabel: 'Create account', idLabel: 'Account name', arnService: 'organizations', arnResource: (r) => `account/o-example/${r.id}`, fields: [{ key: 'name', label: 'Account name' }, { key: 'email', label: 'Email' }, { key: 'ou', label: 'OU' }, { key: 'status', label: 'Status', badge: true }], defaults: { email: 'team@example.com', ou: 'Engineering', status: 'ACTIVE' } } },
  },
  servicequotas: {
    title: 'Service Quotas',
    category: 'Management & Governance',
    desc: 'View and manage service limits',
    primary: 'requests',
    resources: { requests: { label: 'Quota requests', createLabel: 'Request quota increase', idLabel: 'Quota request name', arnService: 'servicequotas', arnResource: (r) => `request/${r.id}`, fields: [{ key: 'name', label: 'Quota' }, { key: 'service', label: 'Service' }, { key: 'requested', label: 'Requested value' }, { key: 'status', label: 'Status', badge: true }], defaults: { service: 'EC2', requested: 64, status: 'CASE_OPENED' } } },
  },
  health: {
    title: 'Health Dashboard',
    category: 'Management & Governance',
    desc: 'Personalized AWS service health alerts',
    primary: 'events',
    resources: { events: { label: 'Events', createLabel: 'Create simulated event', idLabel: 'Event title', arnService: 'health', arnResource: (r) => `event/${r.id}`, fields: [{ key: 'name', label: 'Event' }, { key: 'service', label: 'Service' }, { key: 'impact', label: 'Impact' }, { key: 'status', label: 'Status', badge: true }], defaults: { service: 'EC2', impact: 'Informational', status: 'open' } } },
  },
  trustedadvisor: {
    title: 'Trusted Advisor',
    category: 'Management & Governance',
    desc: 'Best-practice checks and recommendations',
    primary: 'checks',
    resources: { checks: { label: 'Checks', createLabel: 'Add simulated check', idLabel: 'Check name', arnService: 'trustedadvisor', arnResource: (r) => `check/${r.id}`, fields: [{ key: 'name', label: 'Check' }, { key: 'category', label: 'Category' }, { key: 'affected', label: 'Affected resources' }, { key: 'status', label: 'Status', badge: true }], defaults: { category: 'Security', affected: 0, status: 'OK' } } },
  },
  wellarchitected: {
    title: 'Well-Architected Tool',
    category: 'Management & Governance',
    desc: 'Review workloads against AWS best practices',
    primary: 'workloads',
    resources: { workloads: { label: 'Workloads', createLabel: 'Define workload', idLabel: 'Workload name', arnService: 'wellarchitected', arnResource: (r) => `workload/${r.id}`, fields: [{ key: 'name', label: 'Workload' }, { key: 'lenses', label: 'Lenses' }, { key: 'risks', label: 'High risks' }, { key: 'status', label: 'Status', badge: true }], defaults: { lenses: 'AWS Well-Architected Framework', risks: 2, status: 'Active' } } },
  },
}

export const GENERIC_SERVICE_KEYS = Object.keys(SERVICE_CONFIGS)

export function getResourceConfig(serviceKey, resourceKey) {
  return SERVICE_CONFIGS[serviceKey]?.resources?.[resourceKey]
}
