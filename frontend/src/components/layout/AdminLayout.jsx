import { Outlet, Link, useLocation, useNavigate } from 'react-router-dom'
import { useAuthStore } from '../../store/authStore'
import { useThemeStore } from '../../store/themeStore'
import { useState } from 'react'
import {
  LayoutDashboard, Target, Cpu, Users, MonitorPlay, ArrowLeft, Shield, Sun, Moon,
  CreditCard, MessageSquare, Wrench, Menu, X, Ticket, Activity, ScrollText, FileText, Tag, ShieldAlert,
  BarChart3, Building2, Mic2, Award
} from 'lucide-react'

const NAV_GROUPS = [
  {
    label: 'Overview',
    items: [
      { path: '/admin', icon: LayoutDashboard, label: 'Overview' },
      { path: '/admin/analytics', icon: BarChart3, label: 'Analytics' },
      { path: '/admin/monitoring', icon: Activity, label: 'Monitoring' },
      { path: '/admin/security', icon: ShieldAlert, label: 'Security' },
    ],
  },
  {
    label: 'Content',
    items: [
      { path: '/admin/scenarios', icon: Target, label: 'Scenarios' },
      { path: '/admin/technologies', icon: Cpu, label: 'Technologies' },
      { path: '/admin/jira', icon: Ticket, label: 'Jira Tickets' },
      { path: '/admin/interviews', icon: Mic2, label: 'Interviews' },
    ],
  },
  {
    label: 'Users & Billing',
    items: [
      { path: '/admin/users', icon: Users, label: 'Users' },
      { path: '/admin/teams', icon: Building2, label: 'Teams' },
      { path: '/admin/subscriptions', icon: CreditCard, label: 'Subscriptions' },
      { path: '/admin/invoices', icon: FileText, label: 'Invoices' },
      { path: '/admin/coupons', icon: Tag, label: 'Coupons' },
      { path: '/admin/certificates', icon: Award, label: 'Certificates' },
    ],
  },
  {
    label: 'System',
    items: [
      { path: '/admin/labs', icon: MonitorPlay, label: 'Active Labs' },
      { path: '/admin/threads', icon: MessageSquare, label: 'Threads' },
      { path: '/admin/audit-logs', icon: ScrollText, label: 'Audit Logs' },
      { path: '/admin/settings', icon: Wrench, label: 'Settings' },
    ],
  },
]

function SidebarContent({ location, theme, toggleTheme, onNav, navigate }) {
  return (
    <>
      {/* Header */}
      <div className="shrink-0 flex items-center gap-3 px-5 py-5 border-b border-surface-700/30">
        <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-accent-purple to-accent-cyan flex items-center justify-center shadow-lg shadow-accent-purple/25">
          <Shield size={16} className="text-white" />
        </div>
        <div className="flex-1 min-w-0">
          <span className="text-sm font-bold text-white tracking-tight">Admin Panel</span>
          <p className="text-[10px] text-surface-500 mt-0.5">FixitLab Operations</p>
        </div>
        <button
          onClick={toggleTheme}
          className="p-1.5 text-surface-400 hover:text-accent-amber rounded-lg hover:bg-surface-800/60 transition-colors shrink-0"
          aria-label="Toggle theme"
        >
          {theme === 'dark' ? <Sun size={15} /> : <Moon size={15} />}
        </button>
      </div>

      {/* Nav groups */}
      <nav className="flex-1 min-h-0 overflow-y-auto px-3 py-4 space-y-4">
        {NAV_GROUPS.map(group => (
          <div key={group.label}>
            <p className="text-[10px] font-semibold text-surface-600 uppercase tracking-widest px-3 mb-1.5">
              {group.label}
            </p>
            <div className="space-y-0.5">
              {group.items.map(({ path, icon: Icon, label }) => {
                const active = location.pathname === path
                return (
                  <Link
                    key={path}
                    to={path}
                    onClick={onNav}
                    className={`flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm font-medium transition-all ${
                      active
                        ? 'bg-accent-purple/10 text-accent-purple border border-accent-purple/20'
                        : 'text-surface-400 hover:text-surface-100 hover:bg-surface-800/60'
                    }`}
                  >
                    <Icon size={16} className={active ? 'text-accent-purple' : ''} />
                    <span className="truncate">{label}</span>
                    {active && <div className="ml-auto w-1 h-1 rounded-full bg-accent-purple shrink-0" />}
                  </Link>
                )
              })}
            </div>
          </div>
        ))}
      </nav>

      {/* Footer */}
      <div className="shrink-0 p-3 border-t border-surface-700/30 space-y-1">
        <button
          type="button"
          onClick={() => { navigate('/dashboard'); onNav?.() }}
          className="flex items-center gap-2.5 w-full px-3 py-2 rounded-lg text-sm text-surface-400 hover:text-surface-100 hover:bg-surface-800/60 transition-all"
        >
          <ArrowLeft size={15} />
          Back to App
        </button>
      </div>
    </>
  )
}

export default function AdminLayout() {
  const location = useLocation()
  const navigate = useNavigate()
  const { user } = useAuthStore()
  const { theme, toggleTheme } = useThemeStore()
  const [mobileOpen, setMobileOpen] = useState(false)

  return (
    <div className="h-screen flex overflow-hidden bg-surface-950 relative">
      {/* Subtle background — less intense than main app, keeps focus on data */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden z-0">
        <div className="absolute inset-0 bg-gradient-to-br from-accent-purple/3 via-transparent to-accent-cyan/2" />
        <div className="absolute top-0 right-0 w-[600px] h-[600px] rounded-full bg-accent-purple/4 blur-[120px] translate-x-1/4 -translate-y-1/4" />
        <div className="absolute bottom-0 left-0 w-[400px] h-[400px] rounded-full bg-accent-cyan/3 blur-[100px] -translate-x-1/4 translate-y-1/4" />
      </div>

      {/* Desktop sidebar */}
      <aside className="hidden lg:flex lg:flex-col w-56 shrink-0 h-screen border-r border-surface-700/30 bg-surface-900/90 backdrop-blur-xl relative z-10">
        <SidebarContent
          location={location}
          theme={theme}
          toggleTheme={toggleTheme}
          onNav={() => {}}
          navigate={navigate}
        />
      </aside>

      {/* Mobile sidebar overlay */}
      <aside className={`
        lg:hidden fixed inset-y-0 left-0 z-50 w-56 flex flex-col h-screen bg-surface-900/95 backdrop-blur-xl border-r border-surface-700/30
        transform transition-transform duration-300
        ${mobileOpen ? 'translate-x-0' : '-translate-x-full'}
      `}>
        <SidebarContent
          location={location}
          theme={theme}
          toggleTheme={toggleTheme}
          onNav={() => setMobileOpen(false)}
          navigate={navigate}
        />
      </aside>

      {mobileOpen && (
        <div className="fixed inset-0 bg-black/60 z-40 lg:hidden" onClick={() => setMobileOpen(false)} />
      )}

      {/* Main content */}
      <div className="flex-1 flex flex-col min-w-0 min-h-0 relative z-10">
        {/* Mobile header */}
        <header className="shrink-0 lg:hidden flex items-center gap-3 px-4 py-3 border-b border-surface-700/30 bg-surface-900/90 backdrop-blur-xl">
          <button type="button" onClick={() => setMobileOpen(!mobileOpen)} className="p-2 text-surface-400 hover:text-white">
            {mobileOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
          <Shield size={16} className="text-accent-purple" />
          <span className="font-bold text-white text-sm">Admin Panel</span>
        </header>

        <main className="flex-1 min-h-0 overflow-y-auto overflow-x-hidden p-4 sm:p-6 lg:p-8">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
