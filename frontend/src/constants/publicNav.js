/**
 * Shared public marketing navigation links.
 * PRIMARY is the desktop header row — kept to the essential destinations so the
 * header never overflows / forces a horizontal scrollbar on narrow laptops.
 * Less-used links live in SECONDARY (mobile drawer + footer only).
 */
export const PUBLIC_NAV_PRIMARY = [
  { to: '/pricing', label: 'Pricing' },
  { to: '/tutorials', label: 'Tutorials' },
  { to: '/certifications', label: 'Certifications' },
  { to: '/mock-interviews', label: 'Mock Interviews' },
  { to: '/verify-certificate', label: 'Verify Certificate' },
  { to: '/#tech', label: 'Technologies' },
]

export const PUBLIC_NAV_SECONDARY = [
  { to: '/simulators', label: 'Lab Consoles' },
  { to: '/about', label: 'About' },
  { to: '/blog', label: 'Blog' },
  { to: '/changelog', label: 'Changelog' },
  { to: '/faq', label: 'FAQ' },
  { to: '/contact', label: 'Contact' },
]

/** All links — mobile drawer and footer */
export const PUBLIC_NAV_LINKS = [...PUBLIC_NAV_PRIMARY, ...PUBLIC_NAV_SECONDARY]
