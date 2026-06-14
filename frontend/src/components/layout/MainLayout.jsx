import { Outlet, Link, useLocation, useNavigate } from 'react-router-dom'
import { useAuthStore } from '../../store/authStore'
import { useThemeStore } from '../../store/themeStore'
import {
  LayoutDashboard, Target, Trophy, User, LogOut, Shield, Menu, X, Bookmark, Layers, Sun, Moon, History, Award, MessageSquare, AlertTriangle, Search
} from 'lucide-react'
import { useState, useEffect, useRef } from 'react'
import NotificationBell from './NotificationBell'
import api from '../../api/client'
import { PlatformBanners } from '../PlatformBanners'

const navItems = [
  { path: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
  { path: '/technologies', icon: Layers, label: 'Technologies' },
  { path: '/scenarios', icon: Target, label: 'All Scenarios' },
  { path: '/leaderboard', icon: Trophy, label: 'Leaderboard' },
  { path: '/achievements', icon: Award, label: 'Achievements' },
  { path: '/bookmarks', icon: Bookmark, label: 'Bookmarks' },
  { path: '/community', icon: MessageSquare, label: 'Community' },
  { path: '/lab-history', icon: History, label: 'Lab History' },
  { path: '/team', icon: Shield, label: 'My Team' },
  { path: '/profile', icon: User, label: 'Profile' },
]

export default function MainLayout() {
  const { user, logout } = useAuthStore()
  const { theme, toggleTheme } = useThemeStore()
  const location = useLocation()
  const navigate = useNavigate()
  const [mobileOpen, setMobileOpen] = useState(false)
  const [maintenanceBanner, setMaintenanceBanner] = useState(null)
  const [platformConfig, setPlatformConfig] = useState(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState(null)
  const [searchOpen, setSearchOpen] = useState(false)
  const searchRef = useRef(null)

  useEffect(() => {
    api.get('/config/').then(res => {
      setPlatformConfig(res.data)
      if (res.data?.maintenance_mode) {
        setMaintenanceBanner(res.data.maintenance_message || 'Platform is under maintenance.')
      }
    }).catch(() => {})
  }, [])

  const isLabRoute = location.pathname.startsWith('/lab/')

  // Search with debounce
  useEffect(() => {
    if (!searchQuery || searchQuery.length < 2) { setSearchResults(null); return }
    const timer = setTimeout(() => {
      api.get(`/search/?q=${encodeURIComponent(searchQuery)}`)
        .then(res => setSearchResults(res.data))
        .catch(() => setSearchResults({ scenarios: [], users: [] }))
    }, 300)
    return () => clearTimeout(timer)
  }, [searchQuery])

  // Close search on click outside
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
    <div className="min-h-screen bg-surface-950 flex relative">
      {/* Background decorations — rich layered effects */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden z-0">
        {/* Mesh gradient base */}
        <div className="absolute inset-0 bg-mesh-gradient opacity-80" />

        {/* Glow orbs — positioned around the viewport */}
        <div className="glow-orb-cyan absolute -top-40 -right-40 animate-float" />
        <div className="glow-orb-purple absolute bottom-0 -left-40 animate-float-delayed" />
        <div className="glow-orb-blue absolute top-1/2 left-1/3 -translate-y-1/2 animate-morph" />
        <div className="glow-orb-pink absolute top-20 right-1/4 animate-float" style={{ animationDelay: '2s' }} />
        <div className="glow-orb-green absolute bottom-1/4 right-0 animate-morph" style={{ animationDelay: '4s' }} />
        <div className="glow-orb-cyan absolute -bottom-60 left-1/2 opacity-40 animate-float-delayed" style={{ animationDelay: '1s' }} />

        {/* Rotating dashed ring — subtle depth */}
        <div className="absolute top-1/2 left-2/3 -translate-x-1/2 -translate-y-1/2 w-[700px] h-[700px] opacity-[0.04] animate-rotate-slow pointer-events-none">
          <div className="w-full h-full rounded-full border-2 border-dashed border-accent-cyan" />
        </div>

        {/* Floating particles */}
        {[...Array(10)].map((_, i) => (
          <div key={i} className="particle" style={{
            width: `${2 + (i % 3) * 2}px`, height: `${2 + (i % 3) * 2}px`,
            background: i % 3 === 0 ? 'rgb(var(--a-cyan) / 0.4)' : i % 3 === 1 ? 'rgb(var(--a-purple) / 0.35)' : 'rgb(var(--a-green) / 0.35)',
            top: `${8 + i * 9}%`, left: `${5 + i * 9}%`,
            animationDelay: `${i * 0.7}s`, animationDuration: `${7 + i * 0.6}s`,
          }} />
        ))}

        {/* Dot pattern overlay */}
        <div className="absolute inset-0 bg-dots-pattern opacity-[0.035]" />

        {/* Grid pattern — very subtle */}
        <div className="absolute inset-0 bg-grid-pattern opacity-[0.015]" />
      </div>

      {/* Sidebar */}
      <aside className={`
        fixed inset-y-0 left-0 z-50 w-64 bg-surface-900/95 backdrop-blur-xl border-r border-surface-700/30 sidebar-glow
        transform transition-transform duration-300 ease-in-out
        ${mobileOpen ? 'translate-x-0' : '-translate-x-full'}
        lg:translate-x-0 lg:static lg:flex lg:flex-col
      `}>
        <div className="flex items-center gap-3 px-6 py-5 border-b border-surface-700/30">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-accent-cyan to-accent-blue flex items-center justify-center shadow-lg shadow-accent-cyan/25">
            <span className="text-white font-bold text-sm">F</span>
          </div>
          <span className="text-lg font-bold text-white tracking-tight">FixitLab</span>
        </div>

        <nav className="flex-1 px-3 py-4 space-y-1" aria-label="Main navigation">
          {navItems.map(({ path, icon: Icon, label }) => (
            <Link
              key={path}
              to={path}
              onClick={() => setMobileOpen(false)}
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
                onClick={() => setMobileOpen(false)}
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

        <div className="p-3 border-t border-surface-700/50">
          <div className="flex items-center gap-2 px-3 py-2">
            <div className="w-8 h-8 rounded-full bg-gradient-to-br from-accent-cyan to-brand-600 flex items-center justify-center text-xs font-bold text-white">
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
              className="p-1.5 text-surface-400 hover:text-accent-amber transition-colors rounded-lg hover:bg-surface-800"
              aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
              title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
            >
              {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
            </button>
            <NotificationBell />
            <button onClick={handleLogout} className="p-1.5 text-surface-500 hover:text-accent-red transition-colors" aria-label="Logout">
              <LogOut size={16} />
            </button>
          </div>
        </div>
      </aside>

      {/* Mobile overlay */}
      {mobileOpen && (
        <div className="fixed inset-0 bg-black/50 z-40 lg:hidden" onClick={() => setMobileOpen(false)} />
      )}

      {/* Main content */}
      <div className="flex-1 flex flex-col min-h-screen relative z-10">
        {/* Mobile header */}
        <header className="lg:hidden flex items-center gap-3 px-4 py-3 border-b border-surface-700/50 bg-surface-900">
          <button onClick={() => setMobileOpen(!mobileOpen)} className="p-2 text-surface-400" aria-label={mobileOpen ? 'Close menu' : 'Open menu'}>
            {mobileOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
          <span className="font-bold text-white">FixitLab</span>
        </header>

        <PlatformBanners config={platformConfig} showMaintenance={!isLabRoute} showPromo={false} />

        <main className={`flex-1 overflow-y-auto overflow-x-hidden ${isLabRoute ? 'p-0' : 'p-3 sm:p-6 lg:p-8'}`} role="main">
          {!isLabRoute && (
          <div className="mb-4 sm:mb-6 relative" ref={searchRef}>
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
                <button onClick={() => { setSearchQuery(''); setSearchResults(null); setSearchOpen(false) }}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-surface-500 hover:text-surface-300">
                  <X size={14} />
                </button>
              )}
            </div>
            {/* Search Results Dropdown */}
            {searchOpen && searchResults && (
              <div className="absolute top-full left-0 mt-2 w-full max-w-xl bg-surface-900 border border-surface-700/50 rounded-xl shadow-2xl z-50 overflow-hidden">
                {(searchResults.scenarios?.length > 0 || searchResults.results?.length > 0) ? (
                  <div className="max-h-80 overflow-y-auto">
                    {(searchResults.scenarios || searchResults.results || []).map((item, i) => (
                      <Link
                        key={i}
                        to={item.slug ? `/scenarios/${item.slug}` : '#'}
                        onClick={() => { setSearchOpen(false); setSearchQuery('') }}
                        className="flex items-center gap-3 px-4 py-3 hover:bg-surface-800/50 transition-colors border-b border-surface-800/50 last:border-0"
                      >
                        <Target size={16} className="text-accent-cyan shrink-0" />
                        <div className="flex-1 min-w-0">
                          <p className="text-sm text-white truncate">{item.title}</p>
                          <p className="text-xs text-surface-500">{item.difficulty} · {item.category || item.technology}</p>
                        </div>
                      </Link>
                    ))}
                  </div>
                ) : (
                  <div className="px-4 py-6 text-center">
                    <p className="text-sm text-surface-500">No results for &ldquo;{searchQuery}&rdquo;</p>
                  </div>
                )}
              </div>
            )}
          </div>
          )}

          <Outlet />
        </main>
      </div>
    </div>
  )
}
