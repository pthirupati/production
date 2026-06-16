import { Outlet, Link, useLocation, useNavigate } from 'react-router-dom'
import { useAuthStore } from '../../store/authStore'
import { useThemeStore } from '../../store/themeStore'
import {
  LayoutDashboard, Target, Trophy, User, LogOut, Shield, Menu, X, Bookmark, Layers, Sun, Moon, History, Award, MessageSquare, Search, Mic2, CreditCard,
} from 'lucide-react'
import { useState, useEffect, useRef } from 'react'
import NotificationBell from './NotificationBell'
import api from '../../api/client'
import { PlatformBanners } from '../PlatformBanners'

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

function SidebarContent({ navVisible, location, user, theme, toggleTheme, handleLogout, onNavClick }) {
  return (
    <>
      <div className="shrink-0 flex items-center gap-3 px-6 py-5 border-b border-surface-700/30">
        <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-accent-cyan to-accent-blue flex items-center justify-center shadow-lg shadow-accent-cyan/25">
          <span className="text-white font-bold text-sm">F</span>
        </div>
        <span className="text-lg font-bold text-white tracking-tight">FixitLab</span>
      </div>

      <nav className="flex-1 min-h-0 overflow-y-auto px-3 py-4 space-y-1" aria-label="Main navigation">
        {navVisible.map(({ path, icon: Icon, label }) => (
          <Link
            key={path}
            to={path}
            onClick={onNavClick}
            aria-current={location.pathname === path ? 'page' : undefined}
            className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${
              location.pathname === path
                ? 'nav-item-active text-accent-cyan'
                : 'text-surface-400 hover:text-surface-100 hover:bg-surface-800/50'
            }`}
          >
            <Icon size={18} aria-hidden="true" />
            {label}
          </Link>
        ))}

        {user?.is_staff && (
          <>
            <div className="my-3 border-t border-surface-700/50" />
            <Link
              to="/admin"
              onClick={onNavClick}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${
                location.pathname.startsWith('/admin')
                  ? 'bg-accent-purple/10 text-accent-purple border border-accent-purple/20'
                  : 'text-surface-400 hover:text-surface-100 hover:bg-surface-800'
              }`}
            >
              <Shield size={18} />
              Admin Panel
            </Link>
          </>
        )}
      </nav>

      <div className="shrink-0 p-3 border-t border-surface-700/50 bg-surface-900/95">
        <div className="flex items-center gap-2 px-3 py-2">
          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-accent-cyan to-brand-600 flex items-center justify-center text-xs font-bold text-white shrink-0">
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

  useEffect(() => {
    api.get('/config/').then(res => setPlatformConfig(res.data)).catch(() => {})
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
      <div className="fixed inset-0 pointer-events-none overflow-hidden z-0">
        <div className="absolute inset-0 bg-mesh-gradient opacity-80" />
        <div className="glow-orb-cyan absolute -top-40 -right-40 animate-float" />
        <div className="glow-orb-purple absolute bottom-0 -left-40 animate-float-delayed" />
      </div>

      {/* Desktop sidebar — fixed height, nav scrolls internally */}
      <aside className="hidden lg:flex lg:flex-col w-64 shrink-0 h-screen border-r border-surface-700/30 bg-surface-900/95 backdrop-blur-xl sidebar-glow z-30">
        <SidebarContent
          navVisible={navVisible}
          location={location}
          user={user}
          theme={theme}
          toggleTheme={toggleTheme}
          handleLogout={handleLogout}
          onNavClick={() => {}}
        />
      </aside>

      {/* Mobile sidebar overlay */}
      <aside className={`
        lg:hidden fixed inset-y-0 left-0 z-50 w-64 flex flex-col h-screen bg-surface-900/98 backdrop-blur-xl border-r border-surface-700/30
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
        />
      </aside>

      {mobileOpen && (
        <div className="fixed inset-0 bg-black/50 z-40 lg:hidden" onClick={() => setMobileOpen(false)} />
      )}

      {/* Main column — only this area scrolls */}
      <div className="flex-1 flex flex-col min-w-0 min-h-0 relative z-10">
        <header className="shrink-0 z-40 border-b border-surface-700/50 bg-surface-900/95 backdrop-blur-xl">
          <div className="lg:hidden flex items-center gap-3 px-4 py-3">
            <button onClick={() => setMobileOpen(!mobileOpen)} className="p-2 text-surface-400" aria-label="Toggle menu">
              {mobileOpen ? <X size={20} /> : <Menu size={20} />}
            </button>
            <span className="font-bold text-white">FixitLab</span>
          </div>

          <PlatformBanners config={platformConfig} showMaintenance={!isLabRoute} showPromo={false} />

          {!isLabRoute && (
            <div className="px-3 sm:px-6 lg:px-8 py-3 border-t border-surface-800/50" ref={searchRef}>
              <div className="relative max-w-xl">
                <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-surface-500" />
                <input
                  type="text"
                  placeholder="Search scenarios, technologies..."
                  value={searchQuery}
                  onChange={(e) => { setSearchQuery(e.target.value); setSearchOpen(true) }}
                  onFocus={() => setSearchOpen(true)}
                  className="input-field w-full pl-10 pr-4 py-2.5 text-sm"
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
                  <div className="absolute top-full left-0 mt-2 w-full bg-surface-900 border border-surface-700/50 rounded-xl shadow-2xl z-50 overflow-hidden max-h-80 overflow-y-auto">
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
            </div>
          )}
        </header>

        <main className={`flex-1 min-h-0 overflow-y-auto overflow-x-hidden ${isLabRoute ? 'p-0' : 'p-3 sm:p-6 lg:p-8'}`} role="main">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
