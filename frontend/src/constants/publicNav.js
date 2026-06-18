/** Shared public marketing navigation links */
export const PUBLIC_NAV_PRIMARY = [
  { to: '/scenarios', label: 'Scenarios' },
  { to: '/mock-interviews', label: 'Mock Interviews' },
  { to: '/leaderboard', label: 'Leaderboard' },
  { to: '/pricing', label: 'Pricing' },
  { to: '/technologies', label: 'Technology' },
  { to: '/verify-certificate', label: 'Verify Certificate' },
  { to: '/about', label: 'About' },
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
