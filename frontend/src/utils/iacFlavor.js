/** Terraform IaC profile for the Terraform Cloud + workspace IDE simulators. */
export const IAC_PROFILE = {
  binary: 'terraform',
  label: 'Terraform',
  cloudTitle: 'Terraform Cloud',
  accent: '#5c4ee5',
  explorerLabel: 'TERRAFORM',
}

export function getIacProfile() {
  return IAC_PROFILE
}

export function isTerraformLab(scenario) {
  const slug = (scenario?.slug || '').toLowerCase()
  const tech = (scenario?.technology?.slug || '').toLowerCase()
  const sim = (scenario?.simulation_type || '').toLowerCase()
  return (
    sim === 'terraform'
    || tech === 'terraform'
    || slug.includes('terraform')
    || slug.startsWith('aws-')
    || slug.startsWith('iac-')
  )
}
