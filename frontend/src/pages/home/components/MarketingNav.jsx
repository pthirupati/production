import { useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { Terminal, ArrowRight, Menu, X, Sun, Moon } from '../../../ui/eagerIcons'
import { useAuthStore } from '../../../store/authStore'
import { useThemeStore } from '../../../store/themeStore'
import { PlatformBanners } from '../../../components/PlatformBanners'
import { PUBLIC_NAV_PRIMARY, PUBLIC_NAV_LINKS } from '../../../constants/publicNav'

export default function MarketingNav({ navRef, platformConfig }) {
  const { isAuthenticated } = useAuthStore()
  const { theme, toggleTheme } = useThemeStore()
  const [mobileNavOpen, setMobileNavOpen] = useState(false)
  const { pathname } = useLocation()
  const navActive = (to) => pathname === to || (to !== '/' && pathname.startsWith(to))

  return (
    <div className="sticky top-0 z-[60]">
      <header ref={navRef} className="fx-marketing-nav">
        <div className="fx-marketing-nav-inner">
          <Link to="/" className="flex items-center gap-[11px] shrink-0 no-underline">
            <span className="w-[38px] h-[38px] rounded-[11px] flex items-center justify-center bg-gradient-to-br from-[var(--fx-ac)] to-[var(--fx-ac2)] shadow-[0_6px_20px_rgba(109,120,255,.45)]">
              <Terminal size={20} className="text-white" strokeWidth={2} />
            </span>
            <span className="font-display font-extrabold text-xl tracking-tight text-white hidden sm:inline">
              FixitLab
            </span>
          </Link>

          <nav className="fx-marketing-nav-links hidden lg:flex" aria-label="Main navigation">
            {PUBLIC_NAV_PRIMARY.map(({ to, label }) => (
              <Link
                key={to}
                to={to}
                className={`fx-marketing-nav-link ${navActive(to) ? 'fx-marketing-nav-link-active' : ''}`}
              >
                {label}
              </Link>
            ))}
          </nav>

          <div className="flex-1" />

          <button
            type="button"
            className="lg:hidden p-2 text-white/60"
            onClick={() => setMobileNavOpen(v => !v)}
            aria-label="Menu"
          >
            {mobileNavOpen ? <X size={20} /> : <Menu size={20} />}
          </button>

          <button
            onClick={toggleTheme}
            className="p-2 rounded-lg text-white/60 hover:text-white hover:bg-white/5 transition-all"
            aria-label="Toggle theme"
          >
            {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
          </button>

          {isAuthenticated ? (
            <Link to="/dashboard" className="fx-marketing-nav-cta">
              Dashboard <ArrowRight size={15} />
            </Link>
          ) : (
            <>
              <Link to="/login" className="hidden sm:inline text-sm font-medium text-white/70 px-3 py-2 no-underline">
                Sign in
              </Link>
              <Link to="/register" data-magnetic className="fx-marketing-nav-cta">
                Start free <ArrowRight size={15} />
              </Link>
            </>
          )}
        </div>
      </header>

      {mobileNavOpen && (
        <div className="lg:hidden border-t border-white/10 px-4 py-3 flex flex-col gap-2 bg-surface-950/95 dark:bg-[#080a16]/95 max-h-[70vh] overflow-y-auto">
          {PUBLIC_NAV_LINKS.map(({ to, label }) => (
            <Link
              key={to}
              to={to}
              onClick={() => setMobileNavOpen(false)}
              className="text-sm text-surface-400 dark:text-white/70 py-2 no-underline hover:text-surface-100"
            >
              {label}
            </Link>
          ))}
        </div>
      )}

      <PlatformBanners config={platformConfig} showMaintenance showPromo />
    </div>
  )
}
