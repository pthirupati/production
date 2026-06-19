/**
 * Visual catalog for technology cards — matches Claude mockup palette.
 * Merged with API data when available.
 */
export const TECH_CATALOG = [
  { name: 'Linux', slug: 'linux', color: '#feb155', tag: 'Hands-on labs' },
  { name: 'Docker', slug: 'docker', color: '#49b5ff', tag: 'Hands-on labs' },
  { name: 'Kubernetes', slug: 'kubernetes', color: '#6d78ff', tag: 'Hands-on labs' },
  { name: 'AWS', slug: 'aws', color: '#56e0b0', tag: 'Hands-on labs' },
  { name: 'Networking', slug: 'networking', color: '#56e0b0', tag: 'Hands-on labs' },
  { name: 'Databases', slug: 'databases', color: '#f579dd', tag: 'Hands-on labs' },
  { name: 'VMware', slug: 'vmware', color: '#7cc0f0', tag: 'Hands-on labs' },
  { name: 'Security', slug: 'security', color: '#ec6a5e', tag: 'Hands-on labs' },
  { name: 'GPU & NVIDIA', slug: 'gpu-nvidia', color: '#b266e0', coming_soon: true },
]

export function catalogEntryForTech(tech) {
  const bySlug = TECH_CATALOG.find(c => c.slug === tech.slug)
  const byName = TECH_CATALOG.find(c => c.name === tech.name)
  return bySlug || byName || { color: '#6d78ff', tag: 'Hands-on labs' }
}

/** Merge API technologies with catalog defaults so cards always render. */
export function mergeTechnologies(apiList) {
  const list = Array.isArray(apiList) ? apiList : []
  if (list.length > 0) {
    return list.map(t => ({
      ...catalogEntryForTech(t),
      ...t,
      color: t.color || catalogEntryForTech(t).color,
    }))
  }
  return TECH_CATALOG.map((c, i) => ({
    id: `catalog-${c.slug}`,
    ...c,
    is_active: !c.coming_soon,
    scenario_count: 0,
    order: i,
  }))
}

export function sortTechnologies(techs) {
  const available = techs.filter(t => !t.coming_soon)
  const soon = techs.filter(t => t.coming_soon)
  return [...available, ...soon]
}
