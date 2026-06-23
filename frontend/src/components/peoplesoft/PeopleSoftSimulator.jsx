import { useState, useEffect, useCallback } from 'react'
import { peoplesoftApi } from '../../api/peoplesoft'
import toast from 'react-hot-toast'
import {
  LogIn, Server, Users, Workflow, Network, RefreshCw, ArrowLeft,
  Lightbulb, Square, CheckCircle2, AlertTriangle, Lock, Unlock, Play,
} from 'lucide-react'

// Oracle PeopleSoft PIA-styled full-screen simulator. Free/local; all state lives
// in the backend peoplesoft_engine (cache-backed). Mirrors the contract of the
// Windows/Nmap inline-overlay sims: ({ sessionId, scenario, onExit, onStop, onHints }).
const PS_BLUE = '#1b3a5c'
const PS_RED = '#c74634'

const NAV = [
  { key: 'home', label: 'Home', icon: Server },
  { key: 'process', label: 'Process Monitor', icon: Workflow },
  { key: 'security', label: 'Security', icon: Users },
  { key: 'integration', label: 'Integration Broker', icon: Network },
]

export default function PeopleSoftSimulator({ sessionId, scenario, onExit, onStop, onHints }) {
  const [state, setState] = useState(null)
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState('')
  const [section, setSection] = useState('home')
  const [busy, setBusy] = useState(false)
  const slug = scenario?.slug || ''

  const refresh = useCallback(async () => {
    const data = await peoplesoftApi.getState(sessionId, slug)
    if (!data || data.error) { setErr(data?.error || 'Could not load the PeopleSoft environment.'); setState(null) }
    else { setErr(''); setState(data) }
    setLoading(false)
  }, [sessionId, slug])

  useEffect(() => { refresh() }, [refresh])

  const run = useCallback(async (fn, okMsg) => {
    if (busy) return
    setBusy(true)
    try {
      const res = await fn()
      if (res?.ok === false) toast.error(res.error || 'Action rejected')
      else { if (okMsg) toast.success(res?.message || okMsg); }
      if (res?.state) setState(res.state)
      else await refresh()
    } finally { setBusy(false) }
  }, [busy, refresh])

  const w = state?.inventory || {}
  const summary = state?.summary || {}
  const goal = state?.goal || {}
  const loggedIn = w?.session?.logged_in

  // ── Sign-in gate ──
  if (!loading && state && !loggedIn) {
    return (
      <div className="absolute inset-0 z-50 flex items-center justify-center" style={{ background: `linear-gradient(135deg, ${PS_BLUE}, #0d2238)` }}>
        <div className="bg-white rounded-md shadow-2xl w-[380px] overflow-hidden">
          <div className="px-6 py-4 text-white" style={{ background: PS_RED }}>
            <div className="text-lg font-semibold">Oracle PeopleSoft</div>
            <div className="text-xs opacity-90">{summary.env || 'HCM Production'} · PeopleTools {summary.peopletools || '8.60'}</div>
          </div>
          <div className="p-6 space-y-3 text-slate-800">
            <p className="text-sm text-slate-500">Sign in to the PeopleSoft Internet Architecture (PIA).</p>
            <button
              onClick={() => run(() => peoplesoftApi.login(sessionId), 'Signed in to PeopleSoft')}
              disabled={busy}
              className="w-full py-2 rounded text-white font-medium flex items-center justify-center gap-2"
              style={{ background: PS_BLUE }}>
              <LogIn size={16} /> Sign In (PS)
            </button>
            <button onClick={onExit} className="w-full py-1.5 text-sm text-slate-500 hover:text-slate-700">Back to lab</button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="absolute inset-0 z-50 flex flex-col bg-slate-100 text-slate-800">
      {/* Header */}
      <div className="flex items-center justify-between px-4 h-12 text-white shrink-0" style={{ background: PS_BLUE }}>
        <div className="flex items-center gap-2">
          <span className="font-semibold tracking-wide" style={{ color: '#fff' }}>ORACLE</span>
          <span className="text-sm opacity-90">PeopleSoft · {summary.env || ''}</span>
        </div>
        <div className="flex items-center gap-2 text-xs">
          <span className="opacity-90">{summary.current_oprid || 'PS'}</span>
          <button onClick={onHints} className="px-2 py-1 rounded bg-white/15 hover:bg-white/25 flex items-center gap-1"><Lightbulb size={13} /> Hints</button>
          <button onClick={onStop} className="px-2 py-1 rounded bg-white/15 hover:bg-white/25 flex items-center gap-1"><Square size={12} /> Stop</button>
          <button onClick={onExit} className="px-2 py-1 rounded bg-white/15 hover:bg-white/25 flex items-center gap-1"><ArrowLeft size={13} /> Back</button>
        </div>
      </div>

      {/* Objective banner */}
      {goal?.objective && (
        <div className="px-4 py-2 text-sm text-amber-900 bg-amber-100 border-b border-amber-200 flex items-center gap-2">
          <AlertTriangle size={14} /> <strong>{goal.title || 'Task'}:</strong> {goal.objective}
        </div>
      )}

      {err && <div className="px-4 py-2 text-sm text-red-700 bg-red-50">{err}</div>}

      <div className="flex flex-1 min-h-0">
        {/* Left menu tree */}
        <nav className="w-56 bg-white border-r border-slate-200 overflow-y-auto shrink-0">
          {NAV.map(({ key, label, icon: Icon }) => (
            <button key={key} onClick={() => setSection(key)}
              className={`w-full text-left px-4 py-2.5 text-sm flex items-center gap-2 border-l-4 ${section === key ? 'border-[#c74634] bg-slate-50 font-medium' : 'border-transparent hover:bg-slate-50'}`}>
              <Icon size={15} /> {label}
            </button>
          ))}
          <div className="px-4 pt-3 pb-1 text-[11px] uppercase text-slate-400 tracking-wide">Menu</div>
          {(w?.portal?.modules || []).map((mod) => (
            <div key={mod.name} className="text-xs">
              <div className="px-4 py-1.5 text-slate-600 font-medium">{mod.name}</div>
              {(mod.components || []).map((c) => {
                const ok = state?.access?.[c.id]
                return (
                  <button key={c.id} disabled={!ok}
                    onClick={() => run(() => peoplesoftApi.navigate(sessionId, c.id), `Opened ${c.name}`)}
                    className={`w-full text-left pl-7 pr-3 py-1.5 flex items-center gap-1.5 ${ok ? 'hover:bg-slate-50 text-slate-700' : 'text-slate-400 cursor-not-allowed'}`}>
                    {ok ? null : <Lock size={11} />} {c.name}
                  </button>
                )
              })}
            </div>
          ))}
        </nav>

        {/* Main content */}
        <main className="flex-1 overflow-y-auto p-5">
          <div className="flex items-center justify-between mb-4">
            <div className="text-xs text-slate-500">
              {(summary.breadcrumb && summary.breadcrumb.length) ? summary.breadcrumb.join(' > ') : 'Home'}
            </div>
            <button onClick={refresh} className="text-xs text-slate-500 hover:text-slate-700 flex items-center gap-1"><RefreshCw size={12} /> Refresh</button>
          </div>

          {loading && <div className="text-slate-400 text-sm">Loading PeopleSoft…</div>}

          {section === 'home' && !loading && (
            <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {[
                ['Process runs', summary.process_runs_total, `${summary.process_runs_error || 0} error`],
                ['Security roles', summary.roles_total, `${summary.users_locked || 0} users locked`],
                ['IB nodes', summary.ib_nodes_total, `${summary.ib_nodes_down || 0} down`],
                ['Components', summary.components_total, `${summary.modules_total} modules`],
              ].map(([t, v, sub]) => (
                <div key={t} className="bg-white rounded border border-slate-200 p-4">
                  <div className="text-xs text-slate-500">{t}</div>
                  <div className="text-2xl font-semibold text-slate-800">{v ?? '—'}</div>
                  <div className="text-[11px] text-slate-400">{sub}</div>
                </div>
              ))}
            </div>
          )}

          {section === 'process' && !loading && (
            <Table head={['Instance', 'Process', 'Server', 'Status', '']}>
              {(w?.process?.runs || []).map((r) => (
                <tr key={r.instance} className="border-t border-slate-100">
                  <td className="px-3 py-2">{r.instance}</td>
                  <td className="px-3 py-2">{r.name}</td>
                  <td className="px-3 py-2 text-slate-500">{r.server}</td>
                  <td className="px-3 py-2"><StatusPill s={r.status} /></td>
                  <td className="px-3 py-2 text-right">
                    {(r.status === 'error' || r.status === 'cancelled') && (
                      <button onClick={() => run(() => peoplesoftApi.rerunProcess(sessionId, r.instance), `Re-queued instance ${r.instance}`)}
                        className="text-xs px-2 py-1 rounded text-white inline-flex items-center gap-1" style={{ background: PS_BLUE }}>
                        <Play size={11} /> Rerun
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </Table>
          )}

          {section === 'security' && !loading && (
            <div className="space-y-5">
              <Panel title="Users (Operator IDs)">
                <Table head={['OPRID', 'Roles', 'Status', '']}>
                  {(w?.security?.users || []).map((u) => (
                    <tr key={u.oprid} className="border-t border-slate-100">
                      <td className="px-3 py-2 font-mono">{u.oprid}</td>
                      <td className="px-3 py-2 text-slate-500">{(u.roles || []).join(', ') || '—'}</td>
                      <td className="px-3 py-2">{u.locked ? <span className="text-red-600 inline-flex items-center gap-1"><Lock size={11} /> Locked</span> : <span className="text-green-600">Active</span>}</td>
                      <td className="px-3 py-2 text-right space-x-2">
                        {u.locked && <button onClick={() => run(() => peoplesoftApi.unlockUser(sessionId, u.oprid), `Unlocked ${u.oprid}`)} className="text-xs px-2 py-1 rounded bg-slate-700 text-white inline-flex items-center gap-1"><Unlock size={11} /> Unlock</button>}
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
                <p className="text-[11px] text-slate-400 mt-2">Use the menu task and Hints to assign a role / permission to fix access.</p>
              </Panel>
              <Panel title="Permission Lists">
                {(w?.security?.permission_lists || []).map((p) => (
                  <div key={p.name || p} className="text-sm py-1 border-b border-slate-100">
                    <span className="font-mono">{p.name || p}</span>
                    <span className="text-slate-400 text-xs ml-2">{(p.permissions || []).join(', ')}</span>
                  </div>
                ))}
              </Panel>
            </div>
          )}

          {section === 'integration' && !loading && (
            <div className="space-y-5">
              <Panel title="Integration Broker — Nodes">
                <Table head={['Node', 'Status', '']}>
                  {(w?.integration?.nodes || []).map((n) => (
                    <tr key={n.name} className="border-t border-slate-100">
                      <td className="px-3 py-2 font-mono">{n.name}</td>
                      <td className="px-3 py-2"><StatusPill s={n.status === 'active' ? 'success' : 'error'} label={n.status} /></td>
                      <td className="px-3 py-2 text-right">
                        {n.status === 'down' && <button onClick={() => run(() => peoplesoftApi.restartIbNode(sessionId, n.name), `Restarted ${n.name}`)} className="text-xs px-2 py-1 rounded text-white inline-flex items-center gap-1" style={{ background: PS_BLUE }}><RefreshCw size={11} /> Restart</button>}
                      </td>
                    </tr>
                  ))}
                </Table>
              </Panel>
              <Panel title="Services">
                <Table head={['Service', 'Active', '']}>
                  {(w?.integration?.services || []).map((s) => (
                    <tr key={s.name} className="border-t border-slate-100">
                      <td className="px-3 py-2 font-mono">{s.name}</td>
                      <td className="px-3 py-2">{s.active ? <span className="text-green-600">Active</span> : <span className="text-slate-400">Inactive</span>}</td>
                      <td className="px-3 py-2 text-right">
                        {!s.active && <button onClick={() => run(() => peoplesoftApi.activateService(sessionId, s.name), `Activated ${s.name}`)} className="text-xs px-2 py-1 rounded bg-slate-700 text-white">Activate</button>}
                      </td>
                    </tr>
                  ))}
                </Table>
              </Panel>
            </div>
          )}
        </main>
      </div>
    </div>
  )
}

function StatusPill({ s, label }) {
  const map = { success: 'bg-green-100 text-green-700', error: 'bg-red-100 text-red-700', running: 'bg-blue-100 text-blue-700', queued: 'bg-amber-100 text-amber-700', cancelled: 'bg-slate-200 text-slate-600' }
  return <span className={`text-xs px-2 py-0.5 rounded ${map[s] || 'bg-slate-100 text-slate-600'}`}>{label || s}{s === 'success' && <CheckCircle2 size={10} className="inline ml-1" />}</span>
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
