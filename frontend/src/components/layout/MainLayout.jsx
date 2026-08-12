import { Outlet, Link, useLocation, useNavigate } from 'react-router-dom'
import { useAuthStore } from '../../store/authStore'
import { useThemeStore } from '../../store/themeStore'
import {
  LayoutDashboard, Target, Trophy, User, LogOut, Shield, Menu, X, Bookmark, Layers, Sun, Moon, History, Award, MessageSquare, Search, Mic2, CreditCard, Bot, MonitorPlay, Route, FolderKanban,
} from '../../ui/eagerIcons'
import { useState, useEffect, useRef } from 'react'
import NotificationBell from './NotificationBell'
import SupportBotWidget from '../SupportBotWidget'
import api from '../../api/client'
import { authApi } from '../../api/auth'
import { PlatformBanners } from '../PlatformBanners'
import CampaignBanner from '../CampaignBanner'
import { FixitLogo } from '../design'
import { useFetch } from '../../hooks/useFetch'
import { useModalA11y } from '../ConfirmModal'

const navItems = [
  { path: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
  { path: '/technologies', icon: Layers, label: 'Technologies' },
  // /simulators is an authenticated route whose only inbound link used to be the
  // anonymous public nav ("Lab Consoles"), so logged-out users bounced to /login
  // and logged-in users never saw it. Sits next to Technologies because every
  // card on the page links to /technologies/:slug.
  { path: '/simulators', icon: MonitorPlay, label: 'Lab Consoles' },
  { path: '/journeys', icon: Route, label: 'Journeys' },
  { path: '/projects', icon: FolderKanban, label: 'Projects' },
  { path: '/scenarios', icon: Target, label: 'All Scenarios' },
  { path: '/interviews', icon: Mic2, label: 'Interviews' },
  { path: '/leaderboard', icon: Trophy, label: 'Leaderboard' },
  { path: '/achievements', icon: Award, label: 'Achievements' },
  { path: '/subscriptions', icon: CreditCard, label: 'Subscriptions' },
  { path: '/bookmarks', icon: Bookmark, label: 'Bookmarks' },
  { path: '/community', icon: MessageSquare, label: 'Community' },
  { path: '/lab-history', icon: History, label: 'Lab History' },
  { path: '/team', icon: Shield, label: 'My Team' },
  { path: '/profile', icon: User, label: 'Profile' },
]

function openSupportBot() {
  window.dispatchEvent(new CustomEvent('fixitlab-support-open'))
}

function SidebarContent({ navVisible, location, user, theme, toggleTheme, handleLogout, onNavClick, showInterviewPromo }) {
  return (
    <>
      <div className="shrink-0 px-3.5 pt-[18px] pb-4">
        <FixitLogo to="/dashboard" size="md" />
      </div>

      <nav className="flex-1 min-h-0 overflow-y-auto px-2.5 space-y-0.5" aria-label="Main navigation">
        {navVisible.map(({ path, icon: Icon, label }) => {
          const active = location.pathname === path || (path !== '/dashboard' && location.pathname.startsWith(path))
          return (
            <Link
              key={path}
              to={path}
              onClick={onNavClick}
              aria-current={active ? 'page' : undefined}
              className={`sidebar-nav-link ${active ? 'sidebar-nav-active' : 'sidebar-nav-idle'}`}
            >
              <Icon size={18} aria-hidden="true" />
              {label}
            </Link>
          )
        })}

        <button
          type="button"
          onClick={() => { openSupportBot(); onNavClick?.() }}
          className="flex items-center gap-3 px-3 py-2.5 rounded-[11px] text-[13.5px] font-medium transition-all w-full text-white/60 hover:text-white hover:bg-white/[0.05]"
        >
          <Bot size={18} aria-hidden="true" />
          Help & Support
        </button>

        {user?.is_staff && (
          <>
            <div className="my-3 border-t border-white/[0.07]" />
            <Link
              to="/admin"
              onClick={onNavClick}
              className={`sidebar-nav-link ${
                location.pathname.startsWith('/admin')
                  ? 'sidebar-nav-active !border-accent-purple/30 !shadow-[inset_3px_0_0_rgb(var(--a-purple))]'
                  : 'sidebar-nav-idle'
              }`}
            >
              <Shield size={18} />
              Admin Panel
            </Link>
          </>
        )}
      </nav>

      {showInterviewPromo && (
        <div className="shrink-0 px-2.5 pb-3 mt-3">
          <div className="fx-interview-promo">
            <div className="flex items-center gap-2 mb-2">
              <Mic2 size={15} className="text-accent-purple/80" />
              <span className="text-[12.5px] font-bold text-white">Interview Studio</span>
            </div>
            <p className="text-[11.5px] text-white/50 mb-2.5 leading-snug">Free 10-min sample available</p>
            <Link
              to="/interviews"
              onClick={onNavClick}
              className="block text-center text-xs font-semibold py-2 rounded-[9px] text-white bg-gradient-to-br from-accent-purple to-accent-cyan hover:opacity-95 transition-opacity"
            >
              Start practice
            </Link>
          </div>
        </div>
      )}

      <div className="shrink-0 p-2.5 border-t border-white/[0.07] lg:hidden">
        <div className="flex items-center gap-2 px-2 py-2">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-accent-cyan to-accent-purple flex items-center justify-center text-xs font-bold text-white shrink-0">
            {user?.first_name?.[0]?.toUpperCase() || user?.username?.[0]?.toUpperCase() || 'U'}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-surface-200 truncate">
              {user?.first_name ? `${user.first_name} ${user.last_name || ''}`.trim() : user?.username}
            </p>
            <p className="text-xs text-surface-500 truncate">{user?.email}</p>
          </div>
          <button
            type="button"
            onClick={toggleTheme}
            className="p-1.5 min-h-[44px] min-w-[44px] inline-flex items-center justify-center text-surface-400 hover:text-accent-amber transition-colors rounded-lg hover:bg-surface-800 shrink-0"
            aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
          >
            {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
          </button>
          <NotificationBell />
          <button type="button" onClick={handleLogout} className="p-1.5 min-h-[44px] min-w-[44px] inline-flex items-center justify-center text-surface-500 hover:text-accent-red transition-colors shrink-0" aria-label="Logout">
            <LogOut size={16} />
          </button>
        </div>
      </div>
    </>
  )
}

export default function MainLayout() {
  const { user } = useAuthStore()
  const { theme, toggleTheme } = useThemeStore()
  const location = useLocation()
  const navigate = useNavigate()
  const [mobileOpen, setMobileOpen] = useState(false)
  const mobileNavRef = useModalA11y(mobileOpen, () => setMobileOpen(false))
  const { data: platformConfig } = useFetch('/config/', {
    config: { silentError: true },
    initialData: null,
  })
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState(null)
  const [searchOpen, setSearchOpen] = useState(false)
  const [showShortcuts, setShowShortcuts] = useState(false)
  const searchRef = useRef(null)
  const searchInputRef = useRef(null)
  const shortcutsPanelRef = useModalA11y(showShortcuts, () => setShowShortcuts(false))
  const navVisible = navItems.filter(item =>
    item.path !== '/interviews' || platformConfig?.interview_enabled !== false
  )
  const showInterviewPromo = platformConfig?.interview_enabled !== false

  const isLabRoute = location.pathname.startsWith('/lab/')
  const isInterviewRoute = /^\/interviews\/(room|round|async)\//.test(location.pathname)
  const isFullscreenRoute = isLabRoute || isInterviewRoute

  useEffect(() => {
    if (!searchQuery || searchQuery.length < 2) {
      setSearchResults(null)
      return undefined
    }
    const controller = new AbortController()
    const timer = setTimeout(() => {
      api.get(`/search/?q=${encodeURIComponent(searchQuery)}`, { signal: controller.signal })
        .then(res => setSearchResults(res.data))
        .catch((err) => {
          if (controller.signal.aborted || err?.code === 'ERR_CANCELED') return
          setSearchResults({ scenarios: [], users: [] })
        })
    }, 300)
    return () => {
      clearTimeout(timer)
      controller.abort()
    }
  }, [searchQuery])

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (searchRef.current && !searchRef.current.contains(e.target)) {
        setSearchOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  // Global Cmd/Ctrl+K focuses search; `?` opens the app shortcut sheet (X7a).
  useEffect(() => {
    if (isFullscreenRoute) return undefined
    const onKey = (e) => {
      const tag = e.target?.tagName
      const typing = tag === 'INPUT' || tag === 'TEXTAREA' || e.target?.isContentEditable

      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        if (typing && e.target === searchInputRef.current) return
        e.preventDefault()
        searchInputRef.current?.focus()
        setSearchOpen(true)
        return
      }

      if (e.key === '?' && !e.metaKey && !e.ctrlKey && !e.altKey && !typing) {
        e.preventDefault()
        setShowShortcuts((open) => !open)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [isFullscreenRoute])

  const handleLogout = async () => {
    await authApi.logout()
    navigate('/login')
  }

  return (
    <div className="h-screen flex overflow-hidden bg-[#080a16] relative">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:top-2 focus:left-2 focus:px-4 focus:py-2 focus:rounded-md focus:bg-accent-cyan focus:text-surface-950 focus:font-semibold"
      >
        Skip to main content
      </a>
      {/* Subtle ambient glow — reference dashboard uses flat dark, not heavy particles */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden z-0">
        <div className="absolute inset-0 bg-[#080a16]" />
        <div className="absolute top-0 left-1/4 w-[480px] h-[480px] rounded-full bg-accent-cyan/[0.04] blur-[120px]" />
        <div className="absolute bottom-0 right-1/4 w-[400px] h-[400px] rounded-full bg-accent-purple/[0.05] blur-[100px]" />
      </div>

      {/* Desktop sidebar — fixed height, nav scrolls internally */}
      <aside className="hidden lg:flex lg:flex-col w-[248px] shrink-0 h-screen fx-sidebar z-30">
        <SidebarContent
          navVisible={navVisible}
          location={location}
          user={user}
          theme={theme}
          toggleTheme={toggleTheme}
          handleLogout={handleLogout}
          onNavClick={() => {}}
          showInterviewPromo={showInterviewPromo}
        />
      </aside>

      {/* Mobile sidebar overlay */}
      <aside
        ref={mobileNavRef}
        tabIndex={mobileOpen ? -1 : undefined}
        role={mobileOpen ? 'dialog' : undefined}
        aria-modal={mobileOpen ? 'true' : undefined}
        aria-label={mobileOpen ? 'Main navigation' : undefined}
        aria-hidden={!mobileOpen}
        className={`
        lg:hidden fixed inset-y-0 left-0 z-50 w-[248px] flex flex-col h-screen fx-sidebar outline-none
        transform transition-transform duration-300
        ${mobileOpen ? 'translate-x-0' : '-translate-x-full'}
      `}
      >
        <SidebarContent
          navVisible={navVisible}
          location={location}
          user={user}
          theme={theme}
          toggleTheme={toggleTheme}
          handleLogout={handleLogout}
          onNavClick={() => setMobileOpen(false)}
          showInterviewPromo={showInterviewPromo}
        />
      </aside>

      {mobileOpen && (
        <div className="fixed inset-0 bg-black/50 z-40 lg:hidden" onClick={() => setMobileOpen(false)} />
      )}

      {/* Main column — only this area scrolls */}
      <div className="flex-1 flex flex-col min-w-0 min-h-0 relative z-10">
        <header className="sticky top-0 shrink-0 z-40 fx-topbar">
          {/* Mobile toggle + banners */}
          <div className="overflow-x-auto">
            <div className="min-w-max lg:min-w-0">
              <div className="lg:hidden flex items-center gap-3 px-4 py-3">
                <button type="button" onClick={() => setMobileOpen(!mobileOpen)} className="p-2 min-h-[44px] min-w-[44px] inline-flex items-center justify-center text-surface-400" aria-label={mobileOpen ? 'Close menu' : 'Open menu'}>
                  {mobileOpen ? <X size={20} /> : <Menu size={20} />}
                </button>
                <FixitLogo to="/dashboard" size="sm" />
              </div>
              <PlatformBanners config={platformConfig} showMaintenance={!isFullscreenRoute} showPromo={false} />
              {!isFullscreenRoute && <CampaignBanner placement="banner_top" />}
            </div>
          </div>

          {!isFullscreenRoute && (
            <div className="flex items-center gap-4 px-4 sm:px-7 h-[62px]" ref={searchRef}>
              <div className="relative flex-1 max-w-[380px]">
                <Search size={15} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-white/40 pointer-events-none" />
                <input
                  ref={searchInputRef}
                  type="text"
                  placeholder="Search scenarios, technologies… (⌘K)"
                  value={searchQuery}
                  onChange={(e) => { setSearchQuery(e.target.value); setSearchOpen(true) }}
                  onFocus={() => setSearchOpen(true)}
                  aria-keyshortcuts="Meta+K Control+K"
                  className="fx-input"
                />
                {searchQuery && (
                  <button
                    type="button"
                    onClick={() => { setSearchQuery(''); setSearchResults(null); setSearchOpen(false) }}
                    className="absolute right-2 top-1/2 -translate-y-1/2 min-h-[44px] min-w-[44px] inline-flex items-center justify-center text-surface-500 hover:text-surface-300"
                    aria-label="Clear search"
                    title="Clear search"
                  >
                    <X size={14} />
                  </button>
                )}
                {searchOpen && searchResults && (
                  <div className="absolute top-full left-0 mt-2 w-full bg-surface-900 border border-white/10 rounded-xl shadow-2xl z-50 overflow-hidden max-h-80 overflow-y-auto">
                    {(searchResults.scenarios?.length > 0 || searchResults.results?.length > 0) ? (
                      (searchResults.scenarios || searchResults.results || []).map((item, i) => (
                        <Link
                          key={i}
                          to={item.slug ? `/scenarios/${item.slug}` : '#'}
                          onClick={() => { setSearchOpen(false); setSearchQuery('') }}
                          className="flex items-center gap-3 px-4 py-3 hover:bg-surface-800/50 border-b border-surface-800/50 last:border-0"
                        >
                          <Target size={16} className="text-accent-cyan shrink-0" />
                          <div className="min-w-0">
                            <p className="text-sm text-white truncate">{item.title}</p>
                            <p className="text-xs text-surface-500">{item.difficulty} · {item.category || item.technology}</p>
                          </div>
                        </Link>
                      ))
                    ) : (
                      <p className="px-4 py-6 text-sm text-surface-500 text-center">No results for &ldquo;{searchQuery}&rdquo;</p>
                    )}
                  </div>
                )}
              </div>

              <div className="flex-1 hidden sm:block" />

              <div className="hidden lg:flex items-center gap-2.5 shrink-0">
                <button
                  type="button"
                  onClick={() => setShowShortcuts(true)}
                  className="w-10 h-10 rounded-[11px] flex items-center justify-center bg-white/[0.04] border border-white/10 text-white/70 hover:bg-white/[0.09] transition-colors text-sm font-semibold"
                  aria-label="Keyboard shortcuts"
                  title="Keyboard shortcuts (?)"
                >
                  ?
                </button>
                <button
                  type="button"
                  onClick={toggleTheme}
                  className="w-10 h-10 rounded-[11px] flex items-center justify-center bg-white/[0.04] border border-white/10 text-white/70 hover:bg-white/[0.09] transition-colors"
                  aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
                >
                  {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
                </button>
                <NotificationBell variant="topbar" />
                <Link
                  to="/profile"
                  className="flex items-center gap-2.5 pl-1.5 pr-3 py-1 rounded-xl bg-white/[0.04] border border-white/10 hover:bg-white/[0.07] transition-colors"
                >
                  <span className="w-[30px] h-[30px] rounded-lg flex items-center justify-center text-[13px] font-bold text-white bg-gradient-to-br from-accent-cyan to-accent-purple">
                    {user?.first_name?.[0]?.toUpperCase() || user?.username?.[0]?.toUpperCase() || 'U'}
                  </span>
                  <div className="leading-tight hidden xl:block">
                    <p className="text-[13px] font-semibold text-white m-0 truncate max-w-[120px]">
                      {user?.first_name ? `${user.first_name}${user.last_name ? ` ${user.last_name[0]}.` : ''}` : user?.username}
                    </p>
                    <p className="text-[11px] text-white/45 m-0">Member</p>
                  </div>
                </Link>
                <button
                  onClick={handleLogout}
                  className="w-10 h-10 rounded-[11px] flex items-center justify-center bg-white/[0.04] border border-white/10 text-white/50 hover:text-accent-red hover:bg-white/[0.09] transition-colors"
                  aria-label="Logout"
                >
                  <LogOut size={16} />
                </button>
              </div>
            </div>
          )}
        </header>

        <main id="main-content" className={`flex-1 min-h-0 overflow-y-auto overflow-x-hidden ${isFullscreenRoute ? 'p-0' : 'p-3 sm:p-6 lg:p-8'}`} role="main">
          <div className={isFullscreenRoute ? 'h-full min-h-0' : 'max-w-[1180px] w-full mx-auto'}>
            <Outlet />
          </div>
        </main>
      </div>
      <SupportBotWidget />

      {showShortcuts && (
        <div
          className="fixed inset-0 z-[80] flex items-center justify-center bg-black/60 p-4"
          onClick={() => setShowShortcuts(false)}
          role="presentation"
        >
          <div
            ref={shortcutsPanelRef}
            role="dialog"
            aria-modal="true"
            aria-labelledby="app-shortcuts-title"
            className="w-full max-w-md rounded-xl border border-white/10 bg-surface-900 p-5 shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-3 mb-4">
              <h2 id="app-shortcuts-title" className="text-base font-semibold text-white m-0">
                Keyboard shortcuts
              </h2>
              <button
                type="button"
                onClick={() => setShowShortcuts(false)}
                className="min-h-[44px] min-w-[44px] inline-flex items-center justify-center text-surface-400 hover:text-white"
                aria-label="Close shortcuts"
              >
                <X size={18} />
              </button>
            </div>
            <ul className="space-y-2.5 text-sm text-surface-300 m-0 p-0 list-none">
              {[
                ['⌘ / Ctrl + K', 'Focus global search'],
                ['?', 'Toggle this shortcut sheet'],
                ['Esc', 'Close dialogs and menus'],
              ].map(([keys, desc]) => (
                <li key={keys} className="flex items-center justify-between gap-4">
                  <span>{desc}</span>
                  <kbd className="shrink-0 rounded-md border border-white/10 bg-white/[0.04] px-2 py-1 text-[11px] font-medium text-white/80">
                    {keys}
                  </kbd>
                </li>
              ))}
            </ul>
            <p className="mt-4 mb-0 text-xs text-surface-500">
              Inside a lab, press <kbd className="px-1 rounded border border-white/10">?</kbd> for
              lab-specific bindings. AWS and datacenter consoles have their own sheets.
            </p>
          </div>
        </div>
      )}
    </div>
  )
}
