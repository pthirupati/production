// Base path the whole AWS console is mounted under.
import { SERVICE_CONFIGS } from '../pages/generic/serviceConfigs'

export const BASE = '/aws-sim'

const CORE_SERVICES = [
  { key: 'ec2', name: 'EC2', category: 'Compute', desc: 'Virtual Servers in the Cloud', path: `${BASE}/ec2/home`, built: true },
  { key: 's3', name: 'S3', category: 'Storage', desc: 'Scalable Storage in the Cloud', path: `${BASE}/s3`, built: true },
  { key: 'iam', name: 'IAM', category: 'Security, Identity & Compliance', desc: 'Manage access to AWS resources', path: `${BASE}/iam/home`, built: true },
  { key: 'vpc', name: 'VPC', category: 'Networking & Content Delivery', desc: 'Isolated Cloud Resources', path: `${BASE}/vpc/home`, built: true },
  { key: 'cloudwatch', name: 'CloudWatch', category: 'Management & Governance', desc: 'Monitor Resources and Applications', path: `${BASE}/cloudwatch/home`, built: true },
]

const GENERIC_SERVICES = Object.entries(SERVICE_CONFIGS).map(([key, cfg]) => ({
  key,
  name: cfg.title,
  category: cfg.category,
  desc: cfg.desc,
  path: `${BASE}/${key}/home`,
  built: true,
}))

// Every visible service links to a real routed page.
export const SERVICES = [...CORE_SERVICES, ...GENERIC_SERVICES]
  .filter((service, index, arr) => arr.findIndex((x) => x.key === service.key) === index)
  .sort((a, b) => a.name.localeCompare(b.name))

export const SERVICE_CATEGORIES = [
  'Compute', 'Containers', 'Storage', 'Database', 'Networking & Content Delivery',
  'Security, Identity & Compliance', 'Management & Governance', 'Developer Tools',
  'Analytics', 'Application Integration', 'Cloud Financial Management',
]

function genericLeftNav(serviceKey, cfg) {
  return {
    title: cfg.title,
    icon: cfg.category === 'Containers' ? 'Boxes' : cfg.category === 'Database' ? 'Database' : cfg.category === 'Security, Identity & Compliance' ? 'Shield' : cfg.category === 'Application Integration' ? 'Workflow' : 'Box',
    items: [
      { label: `${cfg.title} Dashboard`, path: `${BASE}/${serviceKey}/home` },
      { group: 'Resources' },
      ...Object.entries(cfg.resources).map(([resourceKey, resourceCfg]) => ({ label: resourceCfg.label, path: `${BASE}/${serviceKey}/${resourceKey}` })),
      { group: 'Monitoring' },
      { label: 'Metrics', path: `${BASE}/${serviceKey}/home` },
      { label: 'Events', path: `${BASE}/${serviceKey}/home` },
      { group: 'Settings' },
      { label: 'Tags', path: `${BASE}/${serviceKey}/${cfg.primary}` },
    ],
  }
}

const GENERIC_LEFT_NAV = Object.fromEntries(Object.entries(SERVICE_CONFIGS).map(([key, cfg]) => [key, genericLeftNav(key, cfg)]))

// Left navigation per service. group=true rows are non-clickable section headers.
export const LEFT_NAV = {
  ec2: {
    title: 'EC2', icon: 'Server',
    items: [
      { label: 'EC2 Dashboard', path: `${BASE}/ec2/home` },
      { label: 'EC2 Global View', path: `${BASE}/ec2/home` },
      { label: 'Events', path: `${BASE}/ec2/home` },
      { group: 'Instances' },
      { label: 'Instances', path: `${BASE}/ec2/instances` },
      { label: 'Instance Types', path: `${BASE}/ec2/instances` },
      { label: 'Launch Templates', path: `${BASE}/ec2/instances` },
      { label: 'Spot Requests', path: `${BASE}/ec2/instances` },
      { label: 'Reserved Instances', path: `${BASE}/ec2/instances` },
      { label: 'Dedicated Hosts', path: `${BASE}/ec2/instances` },
      { group: 'Images' },
      { label: 'AMIs', path: `${BASE}/ec2/amis` },
      { group: 'Elastic Block Store' },
      { label: 'Volumes', path: `${BASE}/ec2/volumes` },
      { label: 'Snapshots', path: `${BASE}/ec2/snapshots` },
      { group: 'Network & Security' },
      { label: 'Security Groups', path: `${BASE}/ec2/security-groups` },
      { label: 'Elastic IPs', path: `${BASE}/ec2/elastic-ips` },
      { label: 'Key Pairs', path: `${BASE}/ec2/key-pairs` },
      { label: 'Network Interfaces', path: `${BASE}/ec2/instances` },
      { group: 'Load Balancing' },
      { label: 'Load Balancers', path: `${BASE}/ec2/load-balancers` },
      { label: 'Target Groups', path: `${BASE}/ec2/target-groups` },
      { group: 'Auto Scaling' },
      { label: 'Auto Scaling Groups', path: `${BASE}/ec2/auto-scaling-groups` },
    ],
  },
  s3: {
    title: 'Amazon S3', icon: 'Database',
    items: [
      { label: 'Buckets', path: `${BASE}/s3` },
      { label: 'Access Points', path: `${BASE}/s3` },
      { label: 'Object Lambda Access Points', path: `${BASE}/s3` },
      { label: 'Multi-Region Access Points', path: `${BASE}/s3` },
      { label: 'Batch Operations', path: `${BASE}/s3` },
      { label: 'Storage Lens', path: `${BASE}/s3` },
      { label: 'Block Public Access settings', path: `${BASE}/s3` },
    ],
  },
  iam: {
    title: 'IAM', icon: 'Shield',
    items: [
      { label: 'Dashboard', path: `${BASE}/iam/home` },
      { group: 'Access management' },
      { label: 'User groups', path: `${BASE}/iam/groups` },
      { label: 'Users', path: `${BASE}/iam/users` },
      { label: 'Roles', path: `${BASE}/iam/roles` },
      { label: 'Policies', path: `${BASE}/iam/policies` },
      { label: 'Identity providers', path: `${BASE}/iam/home` },
      { label: 'Account settings', path: `${BASE}/iam/home` },
      { group: 'Access reports' },
      { label: 'Access Analyzer', path: `${BASE}/iam/home` },
      { label: 'Credential report', path: `${BASE}/iam/home` },
    ],
  },
  vpc: {
    title: 'VPC', icon: 'Network',
    items: [
      { label: 'VPC Dashboard', path: `${BASE}/vpc/home` },
      { group: 'Virtual private cloud' },
      { label: 'Your VPCs', path: `${BASE}/vpc/vpcs` },
      { label: 'Subnets', path: `${BASE}/vpc/subnets` },
      { label: 'Route tables', path: `${BASE}/vpc/route-tables` },
      { label: 'Internet gateways', path: `${BASE}/vpc/internet-gateways` },
      { group: 'Security' },
      { label: 'Security groups', path: `${BASE}/vpc/security-groups` },
      { label: 'Network ACLs', path: `${BASE}/vpc/vpcs` },
    ],
  },
  cloudwatch: {
    title: 'CloudWatch', icon: 'Activity',
    items: [
      { label: 'Overview', path: `${BASE}/cloudwatch/home` },
      { group: 'Alarms' },
      { label: 'All alarms', path: `${BASE}/cloudwatch/alarms` },
      { label: 'In alarm', path: `${BASE}/cloudwatch/alarms` },
      { group: 'Metrics' },
      { label: 'All metrics', path: `${BASE}/cloudwatch/home` },
    ],
  },
  ...GENERIC_LEFT_NAV,
}

export const SERVICE_KEYS = Object.keys(LEFT_NAV)
