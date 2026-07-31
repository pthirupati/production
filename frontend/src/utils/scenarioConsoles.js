/**
 * Prefer YAML/API ``consoles`` for primary lab surface selection.
 * Empty / unknown → null so LabRunner keeps slug heuristics.
 */

/** Keys that never select a primary GUI overlay. */
const NON_PRIMARY = new Set(['terminal', 'bmc', 'vmware'])

/**
 * Map YAML console key → LabRunner primarySimKind.
 * Keep in sync with PRIMARY_SIM_COMPONENTS / LabRunner primarySimKind chain.
 */
const CONSOLE_TO_KIND = {
  aws: 'aws',
  azure: 'azure',
  gcp: 'gcp',
  openstack: 'openstack',
  soc: 'soc',
  datacenter: 'datacenter',
  netapp: 'netapp',
  commvault: 'commvault',
  dellemc: 'dellemc',
  windows: 'windows',
  nmap: 'nmap',
  wireshark: 'wireshark',
  grafana: 'monitoring',
  prometheus: 'monitoring',
  monitoring: 'monitoring',
  kubernetes: 'k8s',
  k8s: 'k8s',
  docker: 'docker',
  terraform: 'terraform',
  awx: 'awx',
  ansible: 'awx',
  peoplesoft: 'peoplesoft',
  baremetal: 'baremetal',
  'data-dashboard': 'datadashboard',
  datadashboard: 'datadashboard',
  'ai-agent': 'agent',
  agent: 'agent',
  cicd: 'cicd',
  devops: 'cicd',
  gitops: 'cicd',
}

export function normalizeConsoles(consoles) {
  if (!Array.isArray(consoles)) return []
  return consoles
    .map((c) => String(c || '').trim().toLowerCase())
    .filter(Boolean)
}

/** First console key that maps to a primary overlay kind, or null. */
export function resolvePrimarySimFromConsoles(consoles) {
  for (const key of normalizeConsoles(consoles)) {
    if (NON_PRIMARY.has(key)) continue
    const kind = CONSOLE_TO_KIND[key]
    if (kind) return kind
  }
  return null
}

export function consolesInclude(consoles, key) {
  const want = String(key || '').toLowerCase()
  return normalizeConsoles(consoles).includes(want)
}
