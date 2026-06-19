/** Shared public marketing navigation links */
export const PUBLIC_NAV_PRIMARY = [
  { to: '/pricing', label: 'Pricing' },
  { to: '/mock-interviews', label: 'Mock Interviews' },
  { to: '/#tech', label: 'Technologies' },
  { to: '/about', label: 'About' },
  { to: '/verify-certificate', label: 'Verify Certificate' },
]

export const PUBLIC_NAV_SECONDARY = [
  { to: '/blog', label: 'Blog' },
  { to: '/community', label: 'Community' },
  { to: '/changelog', label: 'Changelog' },
  { to: '/faq', label: 'FAQ' },
  { to: '/contact', label: 'Contact' },
]

/** All links — mobile drawer and footer */
export const PUBLIC_NAV_LINKS = [...PUBLIC_NAV_PRIMARY, ...PUBLIC_NAV_SECONDARY]
