// Maps an EC2 instance (AMI, OS, tags) to a FixitLab lab workload profile so the
// browser SSH terminal can reuse the same Linux / Kubernetes / Windows engines as
// the main lab simulations.

export const WORKLOAD_LABELS = {
  linux: 'Linux administration',
  kubernetes: 'Kubernetes worker',
  windows: 'Windows Server',
}

/** @returns {'linux' | 'kubernetes' | 'windows'} */
export function resolveEc2Workload(instance) {
  if (!instance) return 'linux'
  const explicit = (instance.workload || '').toLowerCase()
  if (explicit === 'kubernetes' || explicit === 'k8s') return 'kubernetes'
  if (explicit === 'windows' || explicit === 'win') return 'windows'
  if (explicit === 'linux') return 'linux'

  const tags = instance.tags || {}
  const tagWorkload = String(
    tags['fixitlab:workload'] || tags.Workload || tags.workload || '',
  ).toLowerCase()
  if (tagWorkload.includes('k8') || tagWorkload.includes('kube')) return 'kubernetes'
  if (tagWorkload.includes('win')) return 'windows'

  const os = (instance.os || '').toLowerCase()
  if (os.includes('windows')) return 'windows'

  const name = String(instance.name || tags.Name || '').toLowerCase()
  if (name.includes('eks') || name.includes('k8s') || name.includes('kube')) return 'kubernetes'
  if (name.includes('windows') || name.includes('win-')) return 'windows'

  return 'linux'
}

export function workloadHint(workload) {
  switch (workload) {
    case 'kubernetes':
      return 'kubectl, systemctl, and container runtime commands are (same engine as FixitLab Kubernetes labs).'
    case 'windows':
      return 'PowerShell session — Get-Service, ipconfig, and Windows admin cmdlets (same engine as FixitLab Windows labs).'
    default:
      return 'Full Linux shell — systemd, LVM, package managers, and editors (same engine as FixitLab Linux labs).'
  }
}
