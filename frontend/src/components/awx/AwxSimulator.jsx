import { useCallback, useEffect, useState } from 'react'
import { awxApi } from '../../api/awx'
import toast from 'react-hot-toast'
import {
  LogIn, Play, RefreshCw, ArrowLeft, Lightbulb, Square, Layers,
  FolderGit2, Key, ListChecks, Server, CheckCircle2, AlertTriangle,
} from 'lucide-react'

const AWX_RED = '#ee0000'

const NAV = [
  { key: 'dashboard', label: 'Dashboard', icon: Layers },
  { key: 'templates', label: 'Templates', icon: ListChecks },
  { key: 'projects', label: 'Projects', icon: FolderGit2 },
  { key: 'inventories', label: 'Inventories', icon: Server },
  { key: 'credentials', label: 'Credentials', icon: Key },
]

export default function AwxSimulator({ sessionId, scenario, onExit, onStop, onHints, onCheck, onExtend, hintsLabel, checkDisabled }) {
  const [state, setState] = useState(null)
  const [loading, setLoading] = useState(true)
  const [section, setSection] = useState('dashboard')
  const [busy, setBusy] = useState(false)
  const slug = scenario?.slug || ''

  const refresh = useCallback(async () => {
    const data = await awxApi.getState(sessionId, slug)
    setState(data)
    setLoading(false)
  }, [sessionId, slug])

  useEffect(() => { refresh() }, [refresh])

  const run = async (fn, okMsg) => {
    if (busy) return
    setBusy(true)
    try {
      const res = await fn()
      if (res?.ok === false) toast.error(res.error || 'Action failed')
      else if (okMsg) toast.success(res?.message || okMsg)
      if (res?.state) setState(res.state)
      else await refresh()
    } finally { setBusy(false) }
  }

  const inv = state?.inventory || {}
  const loggedIn = inv?.session?.logged_in
  const goal = state?.goal || {}

  if (!loading && state && !loggedIn) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#1a1a2e]">
        <div className="bg-white rounded-lg shadow-2xl w-[400px] overflow-hidden">
          <div className="px-6 py-4 text-white font-semibold" style={{ background: AWX_RED }}>Ansible AWX</div>
          <div className="p-6 space-y-3">
            <p className="text-sm text-slate-600">Sign in to Ansible AWX / Tower training instance.</p>
            <button onClick={() => run(() => awxApi.login(sessionId), 'Signed in')} disabled={busy}
              className="w-full py-2 rounded text-white font-medium flex items-center justify-center gap-2" style={{ background: AWX_RED }}>
              <LogIn size={16} /> Sign In
            </button>
            <div className="flex flex-wrap gap-2 pt-2 border-t">
              {onHints && <button onClick={onHints} className="text-xs px-2 py-1 border rounded">{hintsLabel || 'Hints'}</button>}
              {onCheck && <button onClick={onCheck} disabled={checkDisabled} className="text-xs px-2 py-1 border rounded">Check</button>}
              {onExit && <button onClick={onExit} className="text-xs px-2 py-1 border rounded ml-auto">Back to terminal</button>}
            </div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-[#f4f4f4] text-slate-800">
      <div className="flex items-center justify-between px-4 h-12 text-white shrink-0" style={{ background: AWX_RED }}>
        <span className="font-semibold">Ansible AWX · {inv?.summary?.version || 'Tower'}</span>
        <div className="flex items-center gap-2 text-xs">
          {onHints && <button onClick={onHints} className="px-2 py-1 rounded bg-white/15 flex items-center gap-1"><Lightbulb size={13} /> {hintsLabel || 'Hints'}</button>}
          {onCheck && <button onClick={onCheck} disabled={checkDisabled} className="px-2 py-1 rounded bg-white/15 flex items-center gap-1"><CheckCircle2 size={13} /> Check</button>}
          {onExtend && <button onClick={onExtend} className="px-2 py-1 rounded bg-white/15">+30m</button>}
          {onStop && <button onClick={onStop} className="px-2 py-1 rounded bg-white/15 flex items-center gap-1"><Square size={12} /> Stop</button>}
          {onExit && <button onClick={onExit} className="px-2 py-1 rounded bg-white/15 flex items-center gap-1"><ArrowLeft size={13} /> Terminal</button>}
        </div>
      </div>

      {goal.objective && (
        <div className="px-4 py-2 text-sm bg-amber-50 border-b border-amber-200 flex items-center gap-2">
          <AlertTriangle size={14} className="text-amber-600 shrink-0" />
          <span><strong>{goal.title}:</strong> {goal.objective}</span>
        </div>
      )}

      <div className="flex flex-1 min-h-0">
        <nav className="w-52 bg-[#2c2c54] text-slate-200 shrink-0 py-2">
          {NAV.map(({ key, label, icon: Icon }) => (
            <button key={key} onClick={() => setSection(key)}
              className={`w-full flex items-center gap-2 px-4 py-2.5 text-sm ${section === key ? 'bg-white/10 text-white border-l-2 border-red-500' : 'hover:bg-white/5'}`}>
              <Icon size={15} /> {label}
            </button>
          ))}
        </nav>
        <main className="flex-1 overflow-auto p-5">
          {section === 'dashboard' && (
            <div className="space-y-4">
              {(inv.broken?.awx_not_installed) && (
                <div className="bg-white border rounded p-4 flex items-center justify-between gap-3">
                  <div><div className="font-medium">AWX Operator</div><div className="text-sm text-slate-500">Not installed — run operator install for this cluster.</div></div>
                  <button onClick={() => run(() => awxApi.installAwx(sessionId), 'AWX installed')}
                    className="px-3 py-1.5 rounded text-white text-sm" style={{ background: AWX_RED }}>Install AWX</button>
                </div>
              )}
              <h2 className="text-lg font-semibold">Recent Jobs</h2>
              <table className="w-full text-sm bg-white border rounded">
                <thead><tr className="bg-slate-50 text-left"><th className="p-2">Job</th><th className="p-2">Status</th></tr></thead>
                <tbody>
                  {(inv.jobs || []).map((j) => (
                    <tr key={j.id} className="border-t"><td className="p-2">{j.name}</td>
                      <td className="p-2"><span className={j.status === 'failed' ? 'text-red-600' : 'text-green-600'}>{j.status}</span></td></tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {section === 'templates' && (
            <div className="space-y-3">
              <div className="flex items-center justify-between gap-3">
                <h2 className="text-lg font-semibold">Job Templates</h2>
                {inv.broken?.missing_template && (
                  <button onClick={() => run(() => awxApi.createTemplate(sessionId, 'Site Deploy'), 'Template created')}
                    className="px-3 py-1.5 rounded text-white text-sm" style={{ background: AWX_RED }}>+ New Template</button>
                )}
              </div>
              {(inv.job_templates || []).map((jt) => (
                <div key={jt.id} className="bg-white border rounded p-3 flex items-center justify-between gap-3">
                  <div><div className="font-medium">{jt.name}</div><div className="text-xs text-slate-500">{jt.playbook} · {jt.inventory}</div></div>
                  <button onClick={() => run(() => awxApi.launchTemplate(sessionId, jt.id), 'Job launched')}
                    className="px-3 py-1.5 rounded text-white text-sm flex items-center gap-1" style={{ background: AWX_RED }}>
                    <Play size={14} /> Launch
                  </button>
                </div>
              ))}
            </div>
          )}
          {section === 'projects' && (
            <div className="space-y-3">
              <h2 className="text-lg font-semibold">Projects</h2>
              {(inv.projects || []).map((p) => (
                <div key={p.id} className="bg-white border rounded p-3 flex items-center justify-between">
                  <div><div className="font-medium">{p.name}</div><div className="text-xs text-slate-500">{p.scm_type} · {p.status}</div></div>
                  <button onClick={() => run(() => awxApi.syncProject(sessionId, p.id), 'Synced')}
                    className="px-3 py-1.5 border rounded text-sm flex items-center gap-1"><RefreshCw size={14} /> Sync</button>
                </div>
              ))}
            </div>
          )}
          {section === 'inventories' && (
            <div className="grid gap-3 sm:grid-cols-2">
              {(inv.inventories || []).map((i) => (
                <div key={i.id} className="bg-white border rounded p-4"><div className="font-medium">{i.name}</div><div className="text-sm text-slate-500">{i.hosts} hosts</div></div>
              ))}
            </div>
          )}
          {section === 'credentials' && (
            <div className="space-y-2">
              {inv.broken?.credential_missing && (
                <button onClick={() => run(() => awxApi.attachCredential(sessionId), 'Credential attached')}
                  className="mb-2 px-3 py-1.5 rounded text-white text-sm" style={{ background: AWX_RED }}>Attach Machine credential to template</button>
              )}
              {(inv.credentials || []).map((c) => (
                <div key={c.id} className="bg-white border rounded p-3 flex justify-between"><span>{c.name}</span><span className="text-xs text-slate-500">{c.kind}</span></div>
              ))}
            </div>
          )}
        </main>
      </div>
    </div>
  )
}
