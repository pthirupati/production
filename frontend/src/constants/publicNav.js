/**
 * Shared public marketing navigation links.
 * PRIMARY is the desktop header row — kept to the essential destinations so the
 * header never overflows / forces a horizontal scrollbar on narrow laptops.
 * Less-used links live in SECONDARY (mobile drawer + footer only).
 */
export const PUBLIC_NAV_PRIMARY = [
  { to: '/pricing', label: 'Pricing' },
  { to: '/tutorials', label: 'Tutorials' },
  { to: '/journeys', label: 'Journeys' },
  { to: '/projects', label: 'Projects' },
  { to: '/certifications', label: 'Certifications' },
  { to: '/mock-interviews', label: 'AI Interviews' },
  { to: '/verify-certificate', label: 'Verify Certificate' },
]

// Technologies + About live in the footer (and mobile secondary drawer) so the
// header stays compact. Lab Consoles (/simulators) is removed entirely — it
// duplicated /technologies.
export const PUBLIC_NAV_SECONDARY = [
  { to: '/#tech', label: 'Technologies' },
  { to: '/about', label: 'About' },
  { to: '/blog', label: 'Blog' },
  { to: '/changelog', label: 'Changelog' },
  { to: '/faq', label: 'FAQ' },
  { to: '/contact', label: 'Contact' },
]

/** All links — mobile drawer and footer */
export const PUBLIC_NAV_LINKS = [...PUBLIC_NAV_PRIMARY, ...PUBLIC_NAV_SECONDARY]
