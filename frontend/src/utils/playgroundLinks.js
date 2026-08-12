/**
 * Resolve tutorial playground CTAs to the correct in-app route.
 *
 * Tutorials store a `playground_slug` from the playground catalogue. Most map
 * to a technology detail page (login required). Lab-link playgrounds route to
 * a guided scenario instead.
 */

const PLAYGROUND_TO_TECHNOLOGY = {
  linux: 'linux',
  bash: 'shell-script',
  'shell-script': 'shell-script',
  docker: 'docker',
  kubernetes: 'kubernetes',
  ansible: 'ansible',
  python: 'python',
  javascript: 'javascript',
  java: 'java',
  sql: 'database',
  security: 'security',
  // §C6 — divergent playground_slug taxonomy → canonical Technology.slug
  git: 'devops',
  github: 'devops',
  gitlab: 'devops',
  jenkins: 'devops',
  aiml: 'ai-ml',
  monitoring: 'prometheus',
  mongodb: 'database',
  nginx: 'linux',
  redis: 'database',
  simulation: 'simulation',
  baremetal: 'baremetal',
  gpu: 'gpu',
  html: 'html',
  nodejs: 'nodejs',
  postgresql: 'postgresql',
  sqlite: 'sqlite',
  terraform: 'terraform',
  peoplesoft: 'peoplesoft',
  aws: 'aws',
  networking: 'networking',
}

/** Playground slugs that open the public ephemeral playground (no login). */
const PUBLIC_PLAYGROUND_SLUGS = new Set([
  'linux', 'bash', 'docker', 'kubernetes', 'ansible', 'python', 'javascript', 'sql',
])

/**
 * Best destination for a tutorial "Try it now" / playground button.
 * Prefers the matching technology page; falls back to /playgrounds/:slug.
 */
export function tutorialPlaygroundHref(playgroundSlug, scenarioSlug = '') {
  if (scenarioSlug) return `/scenarios/${scenarioSlug}`
  const tech = PLAYGROUND_TO_TECHNOLOGY[playgroundSlug]
  if (tech) return `/technologies/${tech}`
  if (playgroundSlug) return `/playgrounds/${playgroundSlug}`
  return '/technologies'
}

export function isPublicPlayground(playgroundSlug) {
  return PUBLIC_PLAYGROUND_SLUGS.has(playgroundSlug)
}

export { PLAYGROUND_TO_TECHNOLOGY }
