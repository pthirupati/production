import { Link, useLocation } from 'react-router-dom'
import { useThemeStore } from '../../store/themeStore'
import { useAuthStore } from '../../store/authStore'
import { Sun, Moon, Menu, X, Bot } from '../../ui/eagerIcons'
import { useState, useEffect } from 'react'
import SupportBotWidget from '../SupportBotWidget'
import { PlatformBanners } from '../PlatformBanners'
import api from '../../api/client'
import { PUBLIC_NAV_PRIMARY, PUBLIC_NAV_LINKS } from '../../constants/publicNav'
import BubbleNavLink from '../BubbleNavLink'
import { FixitLogo } from '../design'
import { useModalA11y } from '../ConfirmModal'

const navLinkClass = (active) =>
  active
    ? 'text-sm text-white font-medium whitespace-nowrap'
    : 'text-sm text-surface-400 hover:text-surface-100 whitespace-nowrap transition-colors'

const FOOTER_SECTIONS = [
  {
    title: 'Product',
    links: [
      { to: '/#tech', label: 'Technologies' },
      { to: '/mock-interviews', label: 'AI Interviews' },
      { to: '/pricing', label: 'Pricing' },
      { to: '/register', label: 'Get Started' },
    ],
  },
  {
    title: 'Resources',
    links: [
      { to: '/blog', label: 'Blog' },
      { to: '/faq', label: 'FAQ' },
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
      { to: '/refunds', label: 'Refunds' },
      { to: '/acceptable-use', label: 'Acceptable use' },
    ],
  },
]

export default function PublicLayout({ children }) {
  const { theme, toggleTheme } = useThemeStore()
  const { isAuthenticated } = useAuthStore()
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const mobileNavRef = useModalA11y(mobileMenuOpen, () => setMobileMenuOpen(false))
  const [platformConfig, setPlatformConfig] = useState(null)
  const { pathname } = useLocation()

  useEffect(() => {
    api.get('/config/', { silentError: true }).then(res => setPlatformConfig(res.data)).catch(() => {})
  }, [])

  const isActive = (to) => pathname === to || (to !== '/' && pathname.startsWith(to))

  return (
    <div className="min-h-screen bg-surface-950">
      {/* Same visually-hidden-until-focused treatment as MainLayout so the link
          never shows on marketing pages. z-[60] clears the z-50 fixed nav. */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:z-[60] focus:top-2 focus:left-2 focus:px-4 focus:py-2 focus:rounded-md focus:bg-accent-cyan focus:text-surface-950 focus:font-semibold"
      >
        Skip to main content
      </a>
      <nav className="fixed top-0 w-full z-50 border-b border-white/[0.07] bg-surface-950/[0.88] backdrop-blur-[18px]">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 h-[68px] flex items-center justify-between gap-4">
          <FixitLogo to="/" size="sm" />

          <div className="hidden lg:flex items-center justify-center gap-0 flex-nowrap flex-1 min-w-0 px-1 overflow-x-auto scrollbar-none">
            {PUBLIC_NAV_PRIMARY.map(({ to, label }) => (
              <BubbleNavLink key={to} to={to} active={isActive(to)} size="sm" className="shrink-0 px-2 py-1.5 text-xs xl:text-sm">
                {label}
              </BubbleNavLink>
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
            <button type="button" onClick={() => setMobileMenuOpen(!mobileMenuOpen)} className="lg:hidden p-2 min-h-[44px] min-w-[44px] inline-flex items-center justify-center text-surface-400" aria-label={mobileMenuOpen ? 'Close menu' : 'Open menu'}>
              {mobileMenuOpen ? <X size={20} /> : <Menu size={20} />}
            </button>
          </div>
        </div>

        {mobileMenuOpen && (
          <div
            ref={mobileNavRef}
            tabIndex={-1}
            role="dialog"
            aria-modal="true"
            aria-label="Site navigation"
            className="lg:hidden border-t border-surface-700/50 bg-surface-950/95 backdrop-blur-xl max-h-[70vh] overflow-y-auto outline-none"
          >
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

      <PlatformBanners config={platformConfig} showMaintenance showPromo />

      {/* pt-[68px] clears the fixed nav; scroll-mt keeps the anchor target from
          landing underneath that header when the skip link jumps here. */}
      <main id="main-content" role="main" className="pt-[68px] scroll-mt-[68px]" tabIndex={-1}>
        {children}
      </main>

      <footer className="relative border-t border-surface-700/50 bg-surface-900/40 overflow-hidden">
        <div className="absolute inset-0 aurora-bg opacity-20 pointer-events-none" aria-hidden="true" />
        <div className="relative max-w-7xl mx-auto px-4 sm:px-6 py-12">
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-8">
            <div className="col-span-2 md:col-span-4 lg:col-span-1 mb-2 lg:mb-0">
              <FixitLogo to="/" size="sm" className="mb-3" />
              <p className="text-sm text-surface-400 leading-relaxed max-w-xs">
                Hands-on labs, AI interviews, and verifiable certificates — learn by fixing real systems.
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
