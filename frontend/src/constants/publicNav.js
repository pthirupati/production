/**
 * Shared public marketing navigation links.
 * PRIMARY is shown on every viewport as a single horizontal scrolling row
 * (no wrap). Secondary links live in the overflow menu / footer.
 */
export const PUBLIC_NAV_PRIMARY = [
  { to: '/tutorials', label: 'Tutorials' },
  { to: '/journeys', label: 'Roadmap' },
  { to: '/projects', label: 'Projects' },
  { to: '/certifications', label: 'Certifications' },
  { to: '/mock-interviews', label: 'AI Interviews' },
  { to: '/verify-certificate', label: 'Certificate Verify' },
  { to: '/pricing', label: 'Pricing' },
]

// Technologies + About + misc live in the overflow menu / footer.
export const PUBLIC_NAV_SECONDARY = [
  { to: '/#tech', label: 'Technologies' },
  { to: '/about', label: 'About' },
  { to: '/blog', label: 'Blog' },
  { to: '/changelog', label: 'Changelog' },
  { to: '/faq', label: 'FAQ' },
  { to: '/contact', label: 'Contact' },
]

/** All links — overflow drawer and footer */
export const PUBLIC_NAV_LINKS = [...PUBLIC_NAV_PRIMARY, ...PUBLIC_NAV_SECONDARY]
