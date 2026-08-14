/**
 * Shared public marketing navigation links.
 * PRIMARY is the desktop header row — kept short enough to stay on ONE line
 * at the lg breakpoint (no wrap). Pricing / Technologies / About live in
 * SECONDARY (mobile drawer + footer).
 */
export const PUBLIC_NAV_PRIMARY = [
  { to: '/tutorials', label: 'Tutorials' },
  { to: '/journeys', label: 'Journeys' },
  { to: '/projects', label: 'Projects' },
  { to: '/certifications', label: 'Certifications' },
  { to: '/mock-interviews', label: 'AI Interviews' },
  { to: '/verify-certificate', label: 'Verify' },
]

// Pricing + Technologies + About live in the footer / mobile drawer so the
// header stays a single row. Lab Consoles (/simulators) is removed — it
// duplicated /technologies.
export const PUBLIC_NAV_SECONDARY = [
  { to: '/pricing', label: 'Pricing' },
  { to: '/#tech', label: 'Technologies' },
  { to: '/about', label: 'About' },
  { to: '/blog', label: 'Blog' },
  { to: '/changelog', label: 'Changelog' },
  { to: '/faq', label: 'FAQ' },
  { to: '/contact', label: 'Contact' },
]

/** All links — mobile drawer and footer */
export const PUBLIC_NAV_LINKS = [...PUBLIC_NAV_PRIMARY, ...PUBLIC_NAV_SECONDARY]
