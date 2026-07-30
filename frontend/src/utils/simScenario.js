/**
 * Resolve which in-app simulator a scenario opens (Grafana, Terraform, AWX, etc.).
 */

const SIM_TYPES = {
  'ansible-awx': { label: 'Ansible AWX', short: 'AWX', accent: '#EE0000' },
  grafana: { label: 'Grafana', short: 'Grafana', accent: '#f7913b' },
  prometheus: { label: 'Prometheus', short: 'Prometheus', accent: '#e6522c' },
  monitoring: { label: 'Grafana + Prometheus', short: 'Monitoring', accent: '#f7913b' },
  terraform: { label: 'Terraform Cloud + VS Code IDE', short: 'Terraform', accent: '#7B42BC' },
  aws: { label: 'AWS Management Console', short: 'AWS', accent: '#ff9900' },
  vmware: { label: 'VMware vCenter', short: 'VMware', accent: '#4fa7e8' },
  'windows-server': { label: 'Windows Server GUI', short: 'Windows', accent: '#0078d4' },
  windows: { label: 'Windows Server GUI', short: 'Windows', accent: '#0078d4' },
  peoplesoft: { label: 'PeopleSoft PIA', short: 'PeopleSoft', accent: '#c74634' },
  baremetal: { label: 'Bare Metal / MAAS', short: 'Bare Metal', accent: '#64748b' },
  'data-dashboard': { label: 'Data Dashboard Builder', short: 'Dashboard', accent: '#8b5cf6' },
  'ai-agent': { label: 'AI Agent Workflow', short: 'Agent', accent: '#a855f7' },
  nmap: { label: 'Nmap Scanner', short: 'Nmap', accent: '#22c55e' },
  wireshark: { label: 'Wireshark', short: 'Wireshark', accent: '#1679a7' },
}

function slugHints(slug) {
  const s = (slug || '').toLowerCase()
  if (s.includes('awx') || s.includes('tower') || s.includes('ansible-awx')) return 'ansible-awx'
  if (s.startsWith('grafana-') || s.includes('grafana')) return 'grafana'
  if (s.startsWith('prometheus-') || s.includes('prometheus')) return 'prometheus'
  if (s.startsWith('terraform-') || s.includes('terraform')) return 'terraform'
  if (s.startsWith('win-') || s.includes('windows')) return 'windows'
  if (s.startsWith('ps-') || s.includes('peoplesoft')) return 'peoplesoft'
  if (s.startsWith('agent-')) return 'ai-agent'
  if (s.startsWith('ds-dashboard-')) return 'data-dashboard'
  if (s.includes('nmap')) return 'nmap'
  if (s.includes('wireshark')) return 'wireshark'
  // Console-graded AWS objectives + academy packs open the AWS Management Console.
  // Do NOT map bare aws-* to Terraform — that stole the console from AWS labs
  // (align with isTerraformLab in iacFlavor.js).
  if (
    s.startsWith('academy-aws-')
    || s.startsWith('ec2-')
    || s.startsWith('s3-')
    || s.startsWith('iam-')
    || s.startsWith('aws-console-')
    || s.startsWith('aws-')
  ) return 'aws'
  return null
}

/** @returns {{ key: string, label: string, short: string, accent: string } | null} */
export function getScenarioSimInfo(scenario) {
  if (!scenario) return null
  const simType = (scenario.simulation_type || '').toLowerCase()
  const tech = (scenario.technology?.slug || '').toLowerCase()
  const slug = scenario.slug || ''

  if (scenario.lab_mode !== 'simulation' && !simType && !slugHints(slug)) {
    if (tech === 'grafana' || tech === 'prometheus' || tech === 'terraform') {
      // technology-only fallback
    } else if (!['grafana', 'prometheus', 'terraform', 'ansible', 'vmware', 'windows'].includes(tech)) {
      return null
    }
  }

  let key = simType && SIM_TYPES[simType] ? simType : null
  if (!key && SIM_TYPES[tech]) key = tech
  if (!key) key = slugHints(slug)
  if (!key && tech === 'ansible' && (slug.includes('awx') || slug.includes('tower'))) key = 'ansible-awx'
  if (!key && tech === 'grafana') key = 'grafana'
  if (!key && tech === 'prometheus') key = 'prometheus'
  if (!key && tech === 'terraform') key = 'terraform'
  if (!key && tech === 'vmware') key = 'vmware'

  if (!key || !SIM_TYPES[key]) return null
  return { key, ...SIM_TYPES[key] }
}

export function scenarioOpensSimulator(scenario) {
  return Boolean(getScenarioSimInfo(scenario))
}
