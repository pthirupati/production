/**
 * Visual catalog for technology cards — matches Claude mockup palette.
 * This is the STATIC baseline so the public technology grid, marquee, and
 * pricing grid always render a full, informative catalog even when the API
 * returns no technologies. Live API data is merged on top (see mergeTechnologies):
 * API entries augment / override these defaults, they never replace the baseline.
 *
 * Slugs mirror the backend Technology slugs (seed_scenarios.TECH_META) so links
 * resolve to real scenario filters when data is present.
 */
export const TECH_CATALOG = [
  { name: 'Linux', slug: 'linux', color: '#feb155', tag: 'Hands-on labs', description: 'Diagnose and fix real Linux servers — services, permissions, boot, and systemd.' },
  { name: 'Docker', slug: 'docker', color: '#49b5ff', tag: 'Hands-on labs', description: 'Debug containers, images, networks, and Compose stacks in live environments.' },
  { name: 'Kubernetes', slug: 'kubernetes', color: '#6d78ff', tag: 'Hands-on labs', description: 'Triage pods, deployments, services, and CrashLoopBackOff on real clusters.' },
  { name: 'Networking', slug: 'networking', color: '#56e0b0', tag: 'Hands-on labs', description: 'Resolve DNS, routing, firewall, and connectivity faults across hosts.' },
  { name: 'Databases', slug: 'database', color: '#f579dd', tag: 'Hands-on labs', description: 'Fix connections, replication, slow queries, and recovery on live databases.' },
  { name: 'VMware', slug: 'vmware', color: '#7cc0f0', tag: 'Hands-on labs', description: 'Operate a full vSphere environment — hosts, VMs, datastores, HA, and vMotion.' },
  { name: 'Security', slug: 'security', color: '#ec6a5e', tag: 'Hands-on labs', description: 'Hunt misconfigurations, capture flags, and harden vulnerable systems.' },
  { name: 'Ansible', slug: 'ansible', color: '#ef6f5a', tag: 'Hands-on labs', description: 'Author and debug playbooks, inventories, and idempotent automation.' },
  { name: 'Python', slug: 'python', color: '#5fd0e0', tag: 'Coding IDE', description: 'Solve real coding and scripting tasks in a browser IDE with auto-validation.' },
  { name: 'Java', slug: 'java', color: '#f7a23b', tag: 'Coding IDE', description: 'Build, debug, and test Java code in a full browser IDE with instant checks.' },
  { name: 'Shell Scripting', slug: 'shell-script', color: '#56e0b0', tag: 'Hands-on labs', description: 'Write robust Bash — parsing, loops, traps, and production-grade scripts.' },
  { name: 'Web Servers', slug: 'html', color: '#f579dd', tag: 'Hands-on labs', description: 'Configure Nginx and web stacks — virtual hosts, TLS, and reverse proxies.' },
  { name: 'DevOps', slug: 'devops', color: '#b266e0', tag: 'Hands-on labs', description: 'Practice CI/CD, infrastructure-as-code, and end-to-end delivery pipelines.' },
  { name: 'Prompt Engineering', slug: 'prompt-engineering', color: '#9a7bff', tag: 'Free AI course', price: 0, description: 'Master prompting and AI workflows — free course plus a practical terminal.' },
  { name: 'Bare Metal & IPMI', slug: 'baremetal', color: '#feb155', tag: 'Hands-on labs', description: 'Drive servers over IPMI/BMC — power, sensors, boot order, and remote console.' },
  { name: 'AI Infrastructure Engineering', slug: 'ai-infra', color: '#76b900', tag: 'Hands-on labs', description: 'Separate career track: MAAS, VyOS, LXD, AWX, Packer/ImageDev, cloud-init, GPU sanity (H100/H200/B300/AMD), and Datacenter twin — DCOps / Bare Metal / PSINFRA fleet ops.' },
  { name: 'GPU & NVIDIA', slug: 'gpu', color: '#b266e0', tag: 'Hands-on labs', description: 'Troubleshoot GPU drivers, CUDA, and accelerated compute environments.' },
  { name: 'Grafana', slug: 'grafana', color: '#f7913b', tag: 'Hands-on labs', description: 'Operate Grafana — dashboards, panels, variables, alerting, and contact points.' },
  { name: 'Prometheus', slug: 'prometheus', color: '#e6522c', tag: 'Hands-on labs', description: 'Query PromQL, debug exporters, recording/alerting rules, and Alertmanager routing.' },
  { name: 'Terraform & IaC', slug: 'terraform', color: '#8a63d2', tag: 'Hands-on labs', description: 'Provision and debug infrastructure as code — providers, state, modules, and drift.' },
  { name: 'Windows Server', slug: 'windows', color: '#49b5ff', tag: 'Hands-on labs', description: 'Administer Windows Server — Active Directory, services, networking, and PowerShell.' },
  { name: 'JavaScript', slug: 'javascript', color: '#f7c843', tag: 'Coding IDE', description: 'Solve JavaScript and Node tasks in a browser IDE with instant auto-grading.' },
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
    // Live data drives the list; enrich each entry with catalog visuals/copy as defaults.
    const merged = list.map(t => {
      const base = catalogEntryForTech(t)
      return {
        ...base,
        ...t,
        color: t.color || base.color,
        tag: t.tag || base.tag,
        description: t.description || base.description,
      }
    })
    // Append catalog technologies the API didn't return so the grid stays complete.
    const seen = new Set(merged.map(t => t.slug))
    TECH_CATALOG.forEach((c, i) => {
      if (!seen.has(c.slug)) {
        merged.push({ id: `catalog-${c.slug}`, ...c, is_active: !c.coming_soon, scenario_count: 0, order: 100 + i })
      }
    })
    return merged
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
