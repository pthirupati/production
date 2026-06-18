/** Shared public marketing navigation links */
export const PUBLIC_NAV_PRIMARY = [
  { to: '/scenarios', label: 'Scenarios' },
  { to: '/mock-interviews', label: 'Mock Interviews' },
  { to: '/leaderboard', label: 'Leaderboard' },
  { to: '/pricing', label: 'Pricing' },
]

export const PUBLIC_NAV_SECONDARY = [
  { to: '/about', label: 'About' },
  { to: '/blog', label: 'Blog' },
  { to: '/community', label: 'Community' },
  { to: '/faq', label: 'FAQ' },
  { to: '/verify-certificate', label: 'Verify Certificate' },
  { to: '/contact', label: 'Contact' },
]

/** All links — mobile drawer and footer */
export const PUBLIC_NAV_LINKS = [...PUBLIC_NAV_PRIMARY, ...PUBLIC_NAV_SECONDARY]
