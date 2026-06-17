import { Link, useLocation } from 'react-router-dom'
import { useThemeStore } from '../../store/themeStore'
import { useAuthStore } from '../../store/authStore'
import { Sun, Moon, Terminal, Menu, X, Bot } from 'lucide-react'
import { useState } from 'react'
import SupportBotWidget from '../SupportBotWidget'
import { PUBLIC_NAV_LINKS } from '../../constants/publicNav'
import BubbleNavLink from '../BubbleNavLink'

const navLinkClass = (active) =>
  active
    ? 'text-sm text-white font-medium whitespace-nowrap'
    : 'text-sm text-surface-400 hover:text-surface-100 whitespace-nowrap transition-colors'

const FOOTER_SECTIONS = [
  {
    title: 'Product',
    links: [
      { to: '/scenarios', label: 'Scenarios' },
      { to: '/mock-interviews', label: 'Mock Interviews' },
      { to: '/pricing', label: 'Pricing' },
      { to: '/leaderboard', label: 'Leaderboard' },
      { to: '/technologies', label: 'Technologies' },
    ],
  },
  {
    title: 'Resources',
    links: [
      { to: '/blog', label: 'Blog' },
      { to: '/faq', label: 'FAQ' },
      { to: '/community', label: 'Community' },
      { to: '/verify-certificate', label: 'Verify Certificate' },
    ],
  },
  {
    title: 'Company',
    links: [
      { to: '/about', label: 'About' },
      { to: '/contact', label: 'Contact' },
    ],
  },
  {
    title: 'Legal',
    links: [
      { to: '/privacy', label: 'Privacy' },
      { to: '/terms', label: 'Terms' },
    ],
  },
]

export default function PublicLayout({ children }) {
  const { theme, toggleTheme } = useThemeStore()
  const { isAuthenticated } = useAuthStore()
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const { pathname } = useLocation()

  const isActive = (to) => pathname === to || (to !== '/' && pathname.startsWith(to))

  return (
    <div className="min-h-screen bg-surface-950">
      <nav className="fixed top-0 w-full z-50 border-b border-surface-700/50 bg-surface-950/90 backdrop-blur-xl">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between gap-4">
          <Link to="/" className="flex items-center gap-2 text-lg font-bold font-display tracking-tight shrink-0">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center shadow-lg shadow-accent-cyan/20">
              <Terminal size={18} className="text-white" />
            </div>
            FixitLab
          </Link>

          <div className="hidden lg:flex items-center justify-center gap-0.5 flex-1 min-w-0 px-2">
            {PUBLIC_NAV_LINKS.slice(0, 7).map(({ to, label }) => (
              <BubbleNavLink key={to} to={to} active={isActive(to)} size="md">{label}</BubbleNavLink>
            ))}
          </div>

          <div className="flex items-center gap-2 sm:gap-3 shrink-0">
            <button
              type="button"
              onClick={() => window.dispatchEvent(new CustomEvent('fixitlab-support-open'))}
              className={`${navLinkClass(false)} hidden md:inline-flex items-center gap-1`}
            >
              <Bot size={14} /> Help
            </button>
            <button onClick={toggleTheme} className="p-2 rounded-lg hover:bg-surface-800 transition-colors" aria-label="Toggle theme">
              {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
            </button>
            {isAuthenticated ? (
              <Link to="/dashboard" className="btn-primary text-sm hidden sm:inline-flex">Dashboard</Link>
            ) : (
              <div className="hidden sm:flex items-center gap-2">
                <Link to="/login" className="btn-secondary text-sm">Log In</Link>
                <Link to="/register" className="btn-primary text-sm">Sign Up</Link>
              </div>
            )}
            <button onClick={() => setMobileMenuOpen(!mobileMenuOpen)} className="lg:hidden p-2 text-surface-400" aria-label="Toggle menu">
              {mobileMenuOpen ? <X size={20} /> : <Menu size={20} />}
            </button>
          </div>
        </div>

        {mobileMenuOpen && (
          <div className="lg:hidden border-t border-surface-700/50 bg-surface-950/95 backdrop-blur-xl max-h-[70vh] overflow-y-auto">
            <div className="px-4 py-4 space-y-1">
              {PUBLIC_NAV_LINKS.map(({ to, label }) => (
                <Link
                  key={to}
                  to={to}
                  onClick={() => setMobileMenuOpen(false)}
                  className={`block text-sm py-2.5 px-2 rounded-lg ${isActive(to) ? 'text-white bg-surface-800/60' : 'text-surface-400 hover:text-white hover:bg-surface-800/40'}`}
                >
                  {label}
                </Link>
              ))}
              <div className="pt-3 mt-2 border-t border-surface-700/50 flex flex-col gap-2">
                {isAuthenticated ? (
                  <Link to="/dashboard" onClick={() => setMobileMenuOpen(false)} className="btn-primary text-sm text-center">Dashboard</Link>
                ) : (
                  <>
                    <Link to="/login" onClick={() => setMobileMenuOpen(false)} className="btn-secondary text-sm text-center">Log In</Link>
                    <Link to="/register" onClick={() => setMobileMenuOpen(false)} className="btn-primary text-sm text-center">Sign Up</Link>
                  </>
                )}
              </div>
            </div>
          </div>
        )}
      </nav>

      <main className="pt-16">
        {children}
      </main>

      <footer className="relative border-t border-surface-700/50 bg-surface-900/40 overflow-hidden">
        <div className="absolute inset-0 aurora-bg opacity-20 pointer-events-none" aria-hidden="true" />
        <div className="relative max-w-7xl mx-auto px-4 sm:px-6 py-12">
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-8">
            <div className="col-span-2 md:col-span-4 lg:col-span-1 mb-2 lg:mb-0">
              <Link to="/" className="flex items-center gap-2 font-display font-bold text-white mb-3">
                <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center">
                  <Terminal size={16} className="text-white" />
                </div>
                FixitLab
              </Link>
              <p className="text-sm text-surface-400 leading-relaxed max-w-xs">
                Hands-on labs, AI mock interviews, and verifiable certificates — learn by fixing real systems.
              </p>
            </div>
            {FOOTER_SECTIONS.map(({ title, links }) => (
              <div key={title}>
                <h3 className="font-display font-semibold text-white mb-3 text-sm">{title}</h3>
                <div className="space-y-2 text-sm text-surface-400">
                  {links.map(({ to, label }) => (
                    <Link key={to} to={to} className="block hover:text-surface-100 transition-colors">{label}</Link>
                  ))}
                </div>
              </div>
            ))}
          </div>
          <div className="mt-10 pt-8 border-t border-surface-700/50 flex flex-col sm:flex-row items-center justify-between gap-3 text-sm text-surface-500">
            <p>&copy; {new Date().getFullYear()} FixitLab. All rights reserved.</p>
            <div className="flex items-center gap-4">
              <Link to="/login" className="hover:text-surface-300 transition-colors">Login</Link>
              <Link to="/register" className="hover:text-surface-300 transition-colors">Sign Up</Link>
            </div>
          </div>
        </div>
      </footer>
      <SupportBotWidget />
    </div>
  )
}
