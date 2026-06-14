import { Outlet, Link, useLocation, useNavigate } from 'react-router-dom'
import { useAuthStore } from '../../store/authStore'
import { useThemeStore } from '../../store/themeStore'
import { useState } from 'react'
import {
  LayoutDashboard, Target, Cpu, Users, MonitorPlay, ArrowLeft, Shield, Sun, Moon,
  CreditCard, MessageSquare, Wrench, Menu, X, Ticket, Activity, ScrollText, FileText
} from 'lucide-react'

const adminNav = [
  { path: '/admin', icon: LayoutDashboard, label: 'Overview' },
  { path: '/admin/scenarios', icon: Target, label: 'Scenarios' },
  { path: '/admin/jira', icon: Ticket, label: 'Jira Tickets' },
  { path: '/admin/technologies', icon: Cpu, label: 'Technologies' },
  { path: '/admin/users', icon: Users, label: 'Users' },
  { path: '/admin/labs', icon: MonitorPlay, label: 'Active Labs' },
  { path: '/admin/monitoring', icon: Activity, label: 'Monitoring' },
  { path: '/admin/subscriptions', icon: CreditCard, label: 'Subscriptions' },
  { path: '/admin/invoices', icon: FileText, label: 'Invoices' },
  { path: '/admin/threads', icon: MessageSquare, label: 'Threads' },
  { path: '/admin/audit-logs', icon: ScrollText, label: 'Audit Logs' },
  { path: '/admin/settings', icon: Wrench, label: 'Settings' },
]

export default function AdminLayout() {
  const location = useLocation()
  const navigate = useNavigate()
  const { user } = useAuthStore()
  const { theme, toggleTheme } = useThemeStore()
  const [mobileOpen, setMobileOpen] = useState(false)

  return (
    <div className="min-h-screen bg-surface-950 flex relative">
      {/* Sidebar */}
      <aside className={`
        fixed inset-y-0 left-0 z-50 w-64 bg-surface-900 border-r border-surface-700/50 flex flex-col
        transform transition-transform duration-300
        ${mobileOpen ? 'translate-x-0' : '-translate-x-full'}
        lg:translate-x-0 lg:static
      `}>
        <div className="flex items-center gap-3 px-6 py-5 border-b border-surface-700/50">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-accent-purple to-accent-cyan flex items-center justify-center">
            <Shield size={16} className="text-white" />
          </div>
          <div className="flex-1">
            <span className="text-lg font-bold text-white">Admin</span>
            <p className="text-xs text-surface-500">FixitLab</p>
          </div>
          <button
            onClick={toggleTheme}
            className="p-1.5 text-surface-400 hover:text-accent-amber transition-colors rounded-lg hover:bg-surface-800"
            aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
            title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
          >
            {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
          </button>
        </div>

        <nav className="flex-1 px-3 py-4 space-y-1">
          {adminNav.map(({ path, icon: Icon, label }) => (
            <Link
              key={path}
              to={path}
              onClick={() => setMobileOpen(false)}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${
                location.pathname === path
                  ? 'bg-accent-purple/10 text-accent-purple border border-accent-purple/20'
                  : 'text-surface-400 hover:text-surface-100 hover:bg-surface-800'
              }`}
            >
              <Icon size={18} />
              {label}
            </Link>
          ))}
        </nav>

        <div className="p-3 border-t border-surface-700/50">
          <button
            onClick={() => { navigate('/dashboard'); setMobileOpen(false) }}
            className="flex items-center gap-2 w-full px-3 py-2.5 rounded-lg text-sm text-surface-400 hover:text-surface-100 hover:bg-surface-800 transition-all"
          >
            <ArrowLeft size={16} />
            Back to App
          </button>
        </div>
      </aside>

      {/* Mobile overlay */}
      {mobileOpen && (
        <div className="fixed inset-0 bg-black/50 z-40 lg:hidden" onClick={() => setMobileOpen(false)} />
      )}

      <div className="flex-1 flex flex-col min-h-screen">
        {/* Mobile header */}
        <header className="lg:hidden flex items-center gap-3 px-4 py-3 border-b border-surface-700/50 bg-surface-900">
          <button onClick={() => setMobileOpen(!mobileOpen)} className="p-2 text-surface-400" aria-label="Toggle menu">
            {mobileOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
          <Shield size={16} className="text-accent-purple" />
          <span className="font-bold text-white">Admin</span>
        </header>

        <main className="flex-1 p-4 lg:p-8 overflow-y-auto">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
