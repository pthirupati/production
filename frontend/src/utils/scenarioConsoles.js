/**
 * Prefer YAML/API ``consoles`` for primary lab surface selection.
 * Empty / unknown → null so LabRunner keeps slug heuristics.
 *
 * Companion keys (vyos, packer, lxd, …) never become primarySimKind — they open
 * as overlays with toolbar chips. ``maas`` aliases to baremetal for primary.
 */

/** Keys that never select a primary GUI overlay (always companion / terminal). */
const NON_PRIMARY = new Set(['terminal', 'bmc', 'vmware', 'packer', 'vyos', 'lxd'])

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
  maas: 'baremetal',
  'data-dashboard': 'datadashboard',
  datadashboard: 'datadashboard',
  'ai-agent': 'agent',
  agent: 'agent',
  cicd: 'cicd',
  devops: 'cicd',
  gitops: 'cicd',
}

/** All companion overlay kinds LabRunner can open from chips / auto-open. */
export const COMPANION_KINDS = [
  'awx',
  'baremetal',
  'lxd',
  'vyos',
  'packer',
  'datacenter',
  'aws',
  'azure',
  'gcp',
  'terraform',
]

export function normalizeConsoles(consoles) {
  if (!Array.isArray(consoles)) return []
  return consoles
    .map((c) => String(c || '').trim().toLowerCase())
    .filter(Boolean)
}

/**
 * First console key that maps to a primary overlay kind, or null.
 * When ``vyos`` is listed, never promote baremetal/maas to primary — VyOS stays
 * the intent and MAAS opens only as an explicit companion chip.
 */
export function resolvePrimarySimFromConsoles(consoles) {
  const keys = normalizeConsoles(consoles)
  const hasVyos = keys.includes('vyos')
  for (const key of keys) {
    if (NON_PRIMARY.has(key)) continue
    if (hasVyos && (key === 'baremetal' || key === 'maas')) continue
    const kind = CONSOLE_TO_KIND[key]
    if (kind) return kind
  }
  return null
}

export function consolesInclude(consoles, key) {
  const want = String(key || '').toLowerCase()
  return normalizeConsoles(consoles).includes(want)
}

/**
 * Which companion chips a scenario should advertise from YAML ``consoles``
 * (plus optional tech-level defaults). Does not apply entitlements — LabRunner
 * still gates with techAccess.
 */
export function companionChipsFromConsoles(consoles, { techSlug = '' } = {}) {
  const keys = normalizeConsoles(consoles)
  const tech = String(techSlug || '').toLowerCase()
  const chips = new Set()

  const add = (k) => { if (COMPANION_KINDS.includes(k)) chips.add(k) }

  for (const key of keys) {
    if (key === 'maas' || key === 'baremetal') add('baremetal')
    else if (key === 'ansible') add('awx')
    else if (key === 'bmc') add('datacenter')
    else add(key)
  }

  // AI Infra Engineering is the BM + ImageDev + DCOps career track — always
  // surface the physical / automation companions even when YAML is sparse.
  if (tech === 'ai-infra') {
    add('baremetal')
    add('lxd')
    add('awx')
    add('datacenter')
  }

  return [...chips]
}
