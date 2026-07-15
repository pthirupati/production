import { useState, useEffect, useCallback } from 'react'
import { peoplesoftApi } from '../../api/peoplesoft'
import toast from 'react-hot-toast'
import {
  LogIn, Server, Users, Workflow, Network, RefreshCw, Menu, Bell, Search, HelpCircle, User,
} from 'lucide-react'
import LabChromeBar from '../lab/LabChromeBar'
import { PS_NAV_MENU } from '../../mockData/peoplesoft'
import {
  FluidHome, JobDataComponent, BenefitsEnrollment, PaycheckReview,
  ProcessMonitorTable, PeopleSoftNavMenu, FluidStubPage,
} from './PeopleSoftFluidViews'
import '../../styles/sim-products.css'

const PS_BLUE = '#1b3a5c'
const PS_RED = '#c74634'

const NAV = [
  { key: 'home', label: 'Home', icon: Server },
  { key: 'process', label: 'Process Monitor', icon: Workflow },
  { key: 'security', label: 'Security', icon: Users },
  { key: 'integration', label: 'Integration Broker', icon: Network },
]

export default function PeopleSoftSimulator({
  sessionId, scenario, onExit, onStop, onHints, onCheck, onExtend,
  hintsLabel, checkDisabled, extendDisabled, embedded = false,
}) {
  const [state, setState] = useState(null)
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState('')
  const [section, setSection] = useState('home')
  const [fluidView, setFluidView] = useState(null)
  const [menuOpen, setMenuOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const slug = scenario?.slug || ''

  const refresh = useCallback(async () => {
    const data = await peoplesoftApi.getState(sessionId, slug)
    if (!data || data.error) { setErr(data?.error || 'Could not load the PeopleSoft environment.'); setState(null) }
    else { setErr(''); setState(data) }
    setLoading(false)
  }, [sessionId, slug])

  useEffect(() => { refresh() }, [refresh])

  // While self-service submissions are queued/running on the Process Scheduler,
  // poll so the Process Monitor advances (queued -> running -> success) on
  // wall-clock without the learner having to click Refresh.
  const runningJobs = state?.summary?.process_runs_running || 0
  useEffect(() => {
    if (!runningJobs) return undefined
    const id = setInterval(() => { refresh() }, 3500)
    return () => clearInterval(id)
  }, [runningJobs, refresh])

  const run = useCallback(async (fn, okMsg) => {
    if (busy) return
    setBusy(true)
    try {
      const res = await fn()
      if (res?.ok === false) toast.error(res.error || 'Action rejected')
      else if (okMsg) toast.success(res?.message || okMsg)
      if (res?.state) setState(res.state)
      else await refresh()
    } finally { setBusy(false) }
  }, [busy, refresh])

  const w = state?.inventory || {}
  const summary = state?.summary || {}
  const goal = state?.goal || {}
  const loggedIn = w?.session?.logged_in
  const oprid = summary.current_oprid || w?.session?.oprid || 'PS'
  // Self-service record for the signed-in operator, keyed off current_oprid.
  const essProfile = state?.ess_profile
    || (w?.self_service?.profiles ? w.self_service.profiles[oprid] : null)
    || null
  const benefitPlans = w?.self_service?.benefit_plans
  const benefitSteps = w?.self_service?.benefit_steps

  const handleFluidNav = (id) => {
    setSection('home')
    if (['jobdata', 'benefits', 'pay', 'time', 'directory', 'training', 'expenses', 'jobs'].includes(id)) {
      setFluidView(id)
    } else setFluidView(null)
  }

  const handleNavMenu = (item) => {
    const t = (item || '').toLowerCase()
    if (t.includes('benefit') || t.includes('enrollment')) { handleFluidNav('benefits'); return }
    if (t.includes('pay') || t.includes('payroll')) { handleFluidNav('pay'); return }
    if (t.includes('job') || t.includes('personal') || t.includes('organizational')) { handleFluidNav('jobdata'); return }
    if (t.includes('process') || t.includes('time')) { setSection(t.includes('time') ? 'home' : 'process'); setFluidView(null); return }
    setSection('home')
    setFluidView(null)
  }

  const chrome = (extra) => (
    <LabChromeBar title="Oracle PeopleSoft" subtitle={summary.env || scenario?.title || slug} accent={PS_RED}
      onHints={onHints} onCheck={onCheck} onExtend={onExtend} onStop={onStop}
      onBackToTerminal={embedded ? undefined : onExit} hintsLabel={hintsLabel}
      checkDisabled={checkDisabled} extendDisabled={extendDisabled} {...extra} />
  )

  if (!loading && state && !loggedIn) {
    return (
      <div className={`${embedded ? 'h-full' : 'absolute inset-0'} z-50 flex flex-col ps-fluid`} style={{ background: `linear-gradient(135deg, ${PS_BLUE}, #0d2238)` }}>
        {chrome()}
        <div className="flex-1 flex items-center justify-center p-4">
          <div className="bg-white rounded-md shadow-2xl w-[380px] overflow-hidden">
            <div className="px-6 py-4 text-white" style={{ background: PS_RED }}>
              <div className="text-lg font-semibold">Oracle PeopleSoft</div>
              <div className="text-xs opacity-90">{summary.env || 'HCM Production'} · PeopleTools {summary.peopletools || '8.60'}</div>
            </div>
            <div className="p-6 space-y-3 text-slate-800">
              <p className="text-sm text-slate-500">Sign in to the PeopleSoft Internet Architecture (PIA).</p>
              <button onClick={() => run(() => peoplesoftApi.login(sessionId), 'Signed in to PeopleSoft')} disabled={busy}
                className="w-full py-2 rounded text-white font-medium flex items-center justify-center gap-2" style={{ background: PS_BLUE }}>
                <LogIn size={16} /> Sign In (PS)
              </button>
            </div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className={`${embedded ? 'h-full' : 'absolute inset-0'} z-50 flex flex-col bg-[#eef1f4] text-slate-800 ps-fluid`}>
      {/* Fluid NavBar */}
      <div className="shrink-0 text-white" style={{ background: PS_BLUE }}>
        <div className="flex items-center gap-3 px-3 py-2 border-b border-white/10">
          <button type="button" onClick={() => setMenuOpen(true)} className="p-2 rounded hover:bg-white/10" title="Navigator"><Menu size={18} /></button>
          <span className="font-semibold text-sm">PeopleSoft</span>
          <div className="flex-1 max-w-md mx-4 hidden sm:flex items-center gap-2 bg-white/10 rounded px-3 py-1.5">
            <Search size={14} className="opacity-70" />
            <input placeholder="Global Search" className="bg-transparent border-none outline-none text-sm flex-1 placeholder:text-white/50" />
          </div>
          <button type="button" className="p-2 rounded hover:bg-white/10" title="Notifications"><Bell size={16} /></button>
          <button type="button" className="p-2 rounded hover:bg-white/10" title="Help"><HelpCircle size={16} /></button>
          <span className="text-xs flex items-center gap-1 opacity-90"><User size={14} /> {summary.current_oprid || 'PS'}</span>
        </div>
      </div>

      <LabChromeBar title={`PeopleSoft · ${summary.env || 'PIA'}`} subtitle={scenario?.title || slug} accent={PS_RED}
        className="lab-chrome-bar !text-white shrink-0" onHints={onHints} onCheck={onCheck} onExtend={onExtend}
        onStop={onStop} onBackToTerminal={embedded ? undefined : onExit} hintsLabel={hintsLabel}
        checkDisabled={checkDisabled} extendDisabled={extendDisabled} />

      {goal?.objective && (
        <div className="px-4 py-2 text-sm text-amber-900 bg-amber-100 border-b border-amber-200 flex items-center gap-2 shrink-0">
          <strong>{goal.title || 'Task'}:</strong> {goal.objective}
        </div>
      )}
      {err && <div className="px-4 py-2 text-sm text-red-700 bg-red-50 shrink-0">{err}</div>}

      <PeopleSoftNavMenu open={menuOpen} onClose={() => setMenuOpen(false)} menu={PS_NAV_MENU} onSelect={handleNavMenu} />

      <div className="flex flex-1 min-h-0">
        <nav className="w-52 bg-white border-r border-slate-200 overflow-y-auto shrink-0 hidden md:block">
          {NAV.map(({ key, label, icon: Icon }) => (
            <button key={key} type="button" onClick={() => { setSection(key); setFluidView(null) }}
              className={`w-full text-left px-4 py-2.5 text-sm flex items-center gap-2 border-l-4 ${section === key && !fluidView ? 'border-[#c74634] bg-slate-50 font-medium' : 'border-transparent hover:bg-slate-50'}`}>
              <Icon size={15} /> {label}
            </button>
          ))}
        </nav>

        <main className="flex-1 overflow-y-auto p-5 min-h-0">
          <div className="flex items-center justify-between mb-4">
            <div className="text-xs text-slate-500">
              {(summary.breadcrumb && summary.breadcrumb.length) ? summary.breadcrumb.join(' > ') : 'Home'}
              {fluidView && ` > ${fluidView}`}
            </div>
            <button type="button" onClick={refresh} className="text-xs text-slate-500 hover:text-slate-700 flex items-center gap-1"><RefreshCw size={12} /> Refresh</button>
          </div>

          {loading && <div className="text-slate-400 text-sm">Loading PeopleSoft…</div>}

          {!loading && fluidView === 'jobdata' && (
            <JobDataComponent profile={essProfile} oprid={oprid} busy={busy}
              onSave={() => run(() => peoplesoftApi.action(sessionId, 'save_job_data', { oprid }), 'Job Data saved — process queued')} />
          )}
          {!loading && fluidView === 'benefits' && (
            <BenefitsEnrollment profile={essProfile} plans={benefitPlans} steps={benefitSteps} busy={busy}
              onSubmit={(plan) => run(() => peoplesoftApi.action(sessionId, 'submit_benefits', { oprid, plan }), 'Open Enrollment submitted — process queued')} />
          )}
          {!loading && fluidView === 'pay' && (
            <PaycheckReview profile={essProfile} busy={busy}
              onReprint={() => run(() => peoplesoftApi.action(sessionId, 'request_paycheck', { oprid }), 'Pay advice reprint queued')} />
          )}
          {!loading && fluidView === 'time' && <FluidStubPage title="My Time" description="Report hours, view time sheets, and manager approvals." />}
          {!loading && fluidView === 'directory' && <FluidStubPage title="Company Directory" description="Search colleagues by name, department, or location." />}
          {!loading && fluidView === 'training' && <FluidStubPage title="Training" description="Browse learning catalog and assigned courses." />}
          {!loading && fluidView === 'expenses' && <FluidStubPage title="Expenses" description="Submit travel and expense reports for approval." />}
          {!loading && fluidView === 'jobs' && <FluidStubPage title="Job Openings" description="Internal recruiting — view and apply for open positions." />}

          {!loading && !fluidView && section === 'home' && (
            <FluidHome onNavigate={handleFluidNav} />
          )}

          {!loading && !fluidView && section === 'process' && (
            <ProcessMonitorTable runs={w?.process?.runs} busy={busy}
              onRerun={(instance) => run(() => peoplesoftApi.rerunProcess(sessionId, instance), `Re-queued ${instance}`)} />
          )}

          {!loading && !fluidView && section === 'security' && (
            <div className="space-y-5">
              <Panel title="Users (Operator IDs)">
                <Table head={['OPRID', 'Roles', 'Status', '']}>
                  {(w?.security?.users || []).map((u) => (
                    <tr key={u.oprid} className="border-t border-slate-100">
                      <td className="px-3 py-2 font-mono">{u.oprid}</td>
                      <td className="px-3 py-2 text-slate-500">{(u.roles || []).join(', ') || '—'}</td>
                      <td className="px-3 py-2">{u.locked ? <span className="text-red-600">Locked</span> : <span className="text-green-600">Active</span>}</td>
                      <td className="px-3 py-2 text-right">
                        {u.locked && (
                          <button type="button" onClick={() => run(() => peoplesoftApi.unlockUser(sessionId, u.oprid), `Unlocked ${u.oprid}`)}
                            className="text-xs px-2 py-1 rounded bg-slate-700 text-white">Unlock</button>
                        )}
                      </td>
                    </tr>
                  ))}
                </Table>
              </Panel>
              <Panel title="Roles">
                <div className="flex flex-wrap gap-2">
                  {(w?.security?.roles || []).map((r) => (
                    <span key={r.name || r} className="text-xs px-2 py-1 rounded bg-slate-100 border border-slate-200">{r.name || r}</span>
                  ))}
                </div>
              </Panel>
            </div>
          )}

          {!loading && !fluidView && section === 'integration' && (
            <Panel title="Integration Broker — Nodes">
              <Table head={['Node', 'Status', '']}>
                {(w?.integration?.nodes || []).map((n) => (
                  <tr key={n.name} className="border-t border-slate-100">
                    <td className="px-3 py-2 font-mono">{n.name}</td>
                    <td className="px-3 py-2">{n.status}</td>
                    <td className="px-3 py-2 text-right">
                      {n.status === 'down' && (
                        <button type="button" onClick={() => run(() => peoplesoftApi.restartIbNode(sessionId, n.name), `Restarted ${n.name}`)}
                          className="text-xs px-2 py-1 rounded text-white" style={{ background: PS_BLUE }}>Restart</button>
                      )}
                    </td>
                  </tr>
                ))}
              </Table>
            </Panel>
          )}
        </main>
      </div>
    </div>
  )
}

function Panel({ title, children }) {
  return (
    <div className="bg-white rounded border border-slate-200">
      <div className="px-3 py-2 text-sm font-medium text-slate-700 border-b border-slate-100">{title}</div>
      <div className="p-3">{children}</div>
    </div>
  )
}

function Table({ head, children }) {
  return (
    <div className="bg-white rounded border border-slate-200 overflow-hidden">
      <table className="w-full text-sm">
        <thead><tr className="bg-slate-50 text-slate-500 text-xs">{head.map((h, i) => <th key={i} className="px-3 py-2 text-left font-medium">{h}</th>)}</tr></thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  )
}
