import { Outlet, Link, useLocation, useNavigate } from 'react-router-dom'
import { useState } from 'react'
import {
  LayoutDashboard, Target, Cpu, Users, MonitorPlay, ArrowLeft, Shield, Menu, X, Ticket, Activity, ScrollText, FileText, Tag, ShieldAlert,
  BarChart3, Building2, Mic2, Award, CreditCard, MessageSquare, Wrench, Megaphone, Briefcase, Boxes, LifeBuoy, Filter,
} from '../../ui/eagerIcons'
import AdminTopbar from './AdminTopbar'
import { useModalA11y } from '../ConfirmModal'

const NAV_GROUPS = [
  {
    label: 'Overview',
    items: [
      { path: '/admin', icon: LayoutDashboard, label: 'Overview' },
      { path: '/admin/analytics', icon: BarChart3, label: 'Analytics' },
      { path: '/admin/funnel', icon: Filter, label: 'Funnel' },
      { path: '/admin/monitoring', icon: Activity, label: 'Monitoring' },
      { path: '/admin/security', icon: ShieldAlert, label: 'Security' },
    ],
  },
  {
    label: 'Content',
    items: [
      { path: '/admin/scenarios', icon: Target, label: 'Scenarios' },
      { path: '/admin/lab-provisioning', icon: Boxes, label: 'Lab Provisioning' },
      { path: '/admin/technologies', icon: Cpu, label: 'Technologies' },
      { path: '/admin/certifications', icon: Award, label: 'Certifications' },
      { path: '/admin/jira', icon: Ticket, label: 'Jira Tickets' },
      { path: '/admin/itsm', icon: LifeBuoy, label: 'ITSM Tickets' },
      { path: '/admin/interviews', icon: Mic2, label: 'Interviews' },
      { path: '/admin/campaigns', icon: Megaphone, label: 'Ads & Campaigns' },
    ],
  },
  {
    label: 'Users & Billing',
    items: [
      { path: '/admin/users', icon: Users, label: 'Users' },
      { path: '/admin/teams', icon: Building2, label: 'Teams' },
      { path: '/admin/subscriptions', icon: CreditCard, label: 'Subscriptions' },
      { path: '/admin/sales', icon: Briefcase, label: 'Sales Inquiries' },
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

function SidebarContent({ location, onNav, navigate }) {
  return (
    <>
      <div className="shrink-0 px-3 pt-[18px] pb-3">
        <Link to="/admin" className="flex items-center gap-2.5 px-2 no-underline" onClick={onNav}>
          <span className="w-[34px] h-[34px] rounded-[9px] flex items-center justify-center bg-gradient-to-br from-accent-purple to-accent-cyan shadow-[0_6px_20px_rgba(178,102,224,.4)]">
            <Shield size={16} className="text-white" />
          </span>
          <div className="leading-tight">
            <span className="block font-display font-extrabold text-base text-white tracking-tight">FixitLab</span>
            <span className="text-[10px] font-semibold uppercase tracking-wider text-accent-purple/80">Admin</span>
          </div>
        </Link>
      </div>

      <div className="h-px bg-white/[0.06] mx-3 mb-3" />

      <nav className="flex-1 min-h-0 overflow-y-auto px-2 space-y-4">
        {NAV_GROUPS.map(group => (
          <div key={group.label}>
            <p className="text-[10px] font-semibold text-white/35 uppercase tracking-widest px-3 mb-1.5">{group.label}</p>
            <div className="space-y-0.5">
              {group.items.map(({ path, icon: Icon, label }) => {
                const active = location.pathname === path
                return (
                  <Link
                    key={path}
                    to={path}
                    onClick={onNav}
                    className={`flex items-center gap-2.5 px-3 py-2 rounded-[9px] text-[13px] font-medium transition-all no-underline ${
                      active
                        ? 'text-white bg-gradient-to-r from-accent-purple/18 to-accent-cyan/8 border border-accent-purple/25 shadow-[inset_0_0_0_1px_rgba(109,120,255,.15)]'
                        : 'text-white/62 hover:text-white hover:bg-white/[0.05]'
                    }`}
                  >
                    <Icon size={16} className={active ? 'text-accent-purple' : 'text-white/50'} />
                    <span className="truncate">{label}</span>
                  </Link>
                )
              })}
            </div>
          </div>
        ))}
      </nav>

      <div className="shrink-0 p-3 mt-auto">
        <button
          type="button"
          onClick={() => { navigate('/dashboard'); onNav?.() }}
          className="flex items-center gap-2 w-full px-3 py-2.5 rounded-[10px] text-xs font-semibold text-white/60 bg-white/[0.04] border border-white/[0.08] hover:bg-white/[0.07] hover:text-white transition-all"
        >
          <ArrowLeft size={14} />
          Exit to app
        </button>
      </div>
    </>
  )
}

export default function AdminLayout() {
  const location = useLocation()
  const navigate = useNavigate()
  const [mobileOpen, setMobileOpen] = useState(false)
  const mobileNavRef = useModalA11y(mobileOpen, () => setMobileOpen(false))

  return (
    <div className="h-screen flex overflow-hidden bg-[#080a16] relative">
      {/* Same visually-hidden-until-focused treatment as MainLayout. z-[60]
          clears the z-50 mobile sidebar drawer. */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:z-[60] focus:top-2 focus:left-2 focus:px-4 focus:py-2 focus:rounded-md focus:bg-accent-cyan focus:text-surface-950 focus:font-semibold"
      >
        Skip to main content
      </a>
      <div className="fixed inset-0 pointer-events-none overflow-hidden z-0">
        <div className="absolute inset-0 bg-[#080a16]" />
        <div className="absolute top-0 right-0 w-[500px] h-[500px] rounded-full bg-accent-purple/[0.05] blur-[120px]" />
      </div>

      <aside className="hidden lg:flex lg:flex-col w-[236px] shrink-0 h-screen fx-admin-sidebar relative z-10">
        <SidebarContent location={location} onNav={() => {}} navigate={navigate} />
      </aside>

      <aside
        ref={mobileNavRef}
        tabIndex={mobileOpen ? -1 : undefined}
        role={mobileOpen ? 'dialog' : undefined}
        aria-modal={mobileOpen ? 'true' : undefined}
        aria-label={mobileOpen ? 'Admin navigation' : undefined}
        aria-hidden={!mobileOpen}
        className={`lg:hidden fixed inset-y-0 left-0 z-50 w-[236px] flex flex-col h-screen fx-admin-sidebar outline-none transform transition-transform duration-300 ${mobileOpen ? 'translate-x-0' : '-translate-x-full'}`}
      >
        <SidebarContent location={location} onNav={() => setMobileOpen(false)} navigate={navigate} />
      </aside>

      {mobileOpen && <div className="fixed inset-0 bg-black/60 z-40 lg:hidden" onClick={() => setMobileOpen(false)} />}

      <div className="flex-1 flex flex-col min-w-0 min-h-0 relative z-10">
        <div className="lg:hidden shrink-0 flex items-center gap-3 px-4 py-3 border-b border-white/[0.07] bg-[#0b0e1d]/90">
          <button type="button" onClick={() => setMobileOpen(!mobileOpen)} className="p-2 min-h-[44px] min-w-[44px] inline-flex items-center justify-center text-white/50" aria-label={mobileOpen ? 'Close admin menu' : 'Open admin menu'}>
            {mobileOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
          <Shield size={16} className="text-accent-purple" />
          <span className="font-bold text-white text-sm">Admin</span>
        </div>

        <AdminTopbar />

        <main id="main-content" role="main" tabIndex={-1} className="flex-1 min-h-0 overflow-y-auto overflow-x-hidden p-4 sm:p-6 lg:px-7 lg:py-[26px]">
          <div className="max-w-[1320px] w-full mx-auto">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  )
}
