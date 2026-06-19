import { Outlet, Link, useLocation, useNavigate } from 'react-router-dom'
import { useAuthStore } from '../../store/authStore'
import { useThemeStore } from '../../store/themeStore'
import {
  LayoutDashboard, Target, Trophy, User, LogOut, Shield, Menu, X, Bookmark, Layers, Sun, Moon, History, Award, MessageSquare, Search, Mic2, CreditCard, Bot,
} from 'lucide-react'
import { useState, useEffect, useRef } from 'react'
import NotificationBell from './NotificationBell'
import SupportBotWidget from '../SupportBotWidget'
import api from '../../api/client'
import { PlatformBanners } from '../PlatformBanners'
import { FixitLogo } from '../design'

const navItems = [
  { path: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
  { path: '/technologies', icon: Layers, label: 'Technologies' },
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
            onClick={toggleTheme}
            className="p-1.5 text-surface-400 hover:text-accent-amber transition-colors rounded-lg hover:bg-surface-800 shrink-0"
            aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
          >
            {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
          </button>
          <NotificationBell />
          <button onClick={handleLogout} className="p-1.5 text-surface-500 hover:text-accent-red transition-colors shrink-0" aria-label="Logout">
            <LogOut size={16} />
          </button>
        </div>
      </div>
    </>
  )
}

export default function MainLayout() {
  const { user, logout } = useAuthStore()
  const { theme, toggleTheme } = useThemeStore()
  const location = useLocation()
  const navigate = useNavigate()
  const [mobileOpen, setMobileOpen] = useState(false)
  const [platformConfig, setPlatformConfig] = useState(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState(null)
  const [searchOpen, setSearchOpen] = useState(false)
  const searchRef = useRef(null)
  const navVisible = navItems.filter(item =>
    item.path !== '/interviews' || platformConfig?.interview_enabled !== false
  )
  const showInterviewPromo = platformConfig?.interview_enabled !== false

  useEffect(() => {
    api.get('/config/', { silentError: true }).then(res => setPlatformConfig(res.data)).catch(() => {})
  }, [])

  const isLabRoute = location.pathname.startsWith('/lab/')

  useEffect(() => {
    if (!searchQuery || searchQuery.length < 2) { setSearchResults(null); return }
    const timer = setTimeout(() => {
      api.get(`/search/?q=${encodeURIComponent(searchQuery)}`)
        .then(res => setSearchResults(res.data))
        .catch(() => setSearchResults({ scenarios: [], users: [] }))
    }, 300)
    return () => clearTimeout(timer)
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

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <div className="h-screen flex overflow-hidden bg-surface-950 relative">
      {/* ═══ GLOBAL IMMERSIVE BACKGROUND ═══ */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden z-0">
        <div className="absolute inset-0 aurora-bg" />
        <div className="dash-orb dash-orb-1" />
        <div className="dash-orb dash-orb-2" />
        <div className="dash-orb dash-orb-3" />
        <div className="dash-orb dash-orb-4" />
        <div className="absolute bottom-0 left-0 right-0 h-[35vh] perspective-grid" />
        <div className="light-beam light-beam-1" />
        <div className="light-beam light-beam-2" />
        <div className="light-beam light-beam-3" />
        {[...Array(12)].map((_, i) => (
          <div key={i} className="dash-particle" style={{
            width: `${2 + (i % 3)}px`, height: `${2 + (i % 3)}px`,
            top: `${5 + (i * 8) % 90}%`, left: `${3 + (i * 9.1) % 94}%`,
            animationDelay: `${i * 0.5}s`, animationDuration: `${7 + (i % 5) * 1.5}s`,
          }} />
        ))}
        <div className="absolute inset-0 hex-grid opacity-[0.012]" />
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
      <aside className={`
        lg:hidden fixed inset-y-0 left-0 z-50 w-[248px] flex flex-col h-screen fx-sidebar
        transform transition-transform duration-300
        ${mobileOpen ? 'translate-x-0' : '-translate-x-full'}
      `}>
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
                <button onClick={() => setMobileOpen(!mobileOpen)} className="p-2 text-surface-400" aria-label="Toggle menu">
                  {mobileOpen ? <X size={20} /> : <Menu size={20} />}
                </button>
                <FixitLogo to="/dashboard" size="sm" />
              </div>
              <PlatformBanners config={platformConfig} showMaintenance={!isLabRoute} showPromo={false} />
            </div>
          </div>

          {!isLabRoute && (
            <div className="flex items-center gap-4 px-4 sm:px-7 h-[62px]" ref={searchRef}>
              <div className="relative flex-1 max-w-[380px]">
                <Search size={15} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-white/40 pointer-events-none" />
                <input
                  type="text"
                  placeholder="Search scenarios, technologies…"
                  value={searchQuery}
                  onChange={(e) => { setSearchQuery(e.target.value); setSearchOpen(true) }}
                  onFocus={() => setSearchOpen(true)}
                  className="fx-input"
                />
                {searchQuery && (
                  <button
                    type="button"
                    onClick={() => { setSearchQuery(''); setSearchResults(null); setSearchOpen(false) }}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-surface-500 hover:text-surface-300"
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

        <main className={`flex-1 min-h-0 overflow-y-auto overflow-x-hidden ${isLabRoute ? 'p-0' : 'p-3 sm:p-6 lg:p-8'}`} role="main">
          <Outlet />
        </main>
      </div>
      <SupportBotWidget />
    </div>
  )
}
