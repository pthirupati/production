import { useCallback, useEffect, useState } from 'react'
import { terraformApi } from '../../api/terraform'
import toast from 'react-hot-toast'
import {
  ArrowLeft, Lightbulb, Square, CheckCircle2, Terminal, Cloud, Play,
  AlertTriangle, RefreshCw,
} from 'lucide-react'

export default function TerraformSimulator({ sessionId, scenario, onExit, onStop, onHints, onCheck, onExtend, hintsLabel, checkDisabled }) {
  const [state, setState] = useState(null)
  const [tab, setTab] = useState('terraform')
  const [awsCmd, setAwsCmd] = useState('aws sts get-caller-identity')
  const [output, setOutput] = useState('')
  const [busy, setBusy] = useState(false)
  const slug = scenario?.slug || ''

  const refresh = useCallback(async () => {
    const data = await terraformApi.getState(sessionId, slug)
    setState(data)
  }, [sessionId, slug])

  useEffect(() => { refresh() }, [refresh])

  const run = async (action, payload = {}, okMsg) => {
    if (busy) return
    setBusy(true)
    try {
      const res = await terraformApi.action(sessionId, action, payload)
      if (res?.ok === false) toast.error(res.error || 'Failed')
      else if (okMsg) toast.success(res?.message || okMsg)
      setOutput(res?.output || res?.plan?.summary || JSON.stringify(res?.plan || res, null, 2) || '')
      if (res?.state) setState(res.state)
      else await refresh()
    } finally { setBusy(false) }
  }

  const tf = state?.state?.terraform || {}
  const goal = state?.state?.goal || {}

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-[#1e1e1e] text-slate-200">
      <div className="flex items-center justify-between px-4 h-11 bg-[#7c3aed] shrink-0">
        <span className="font-semibold text-sm flex items-center gap-2"><Cloud size={16} /> Terraform + AWS CLI</span>
        <div className="flex items-center gap-2 text-xs">
          {onHints && <button onClick={onHints} className="px-2 py-1 rounded bg-white/15 flex items-center gap-1"><Lightbulb size={13} /> {hintsLabel || 'Hints'}</button>}
          {onCheck && <button onClick={onCheck} disabled={checkDisabled} className="px-2 py-1 rounded bg-white/15 flex items-center gap-1"><CheckCircle2 size={13} /> Check</button>}
          {onExtend && <button onClick={onExtend} className="px-2 py-1 rounded bg-white/15">+30m</button>}
          {onStop && <button onClick={onStop} className="px-2 py-1 rounded bg-white/15 flex items-center gap-1"><Square size={12} /> Stop</button>}
          {onExit && <button onClick={onExit} className="px-2 py-1 rounded bg-white/15 flex items-center gap-1"><ArrowLeft size={13} /> Terminal</button>}
        </div>
      </div>

      {goal.objective && (
        <div className="px-4 py-2 text-xs bg-amber-900/40 border-b border-amber-700/50 flex items-center gap-2">
          <AlertTriangle size={13} /> <span>{goal.objective}</span>
        </div>
      )}

      <div className="flex border-b border-slate-700 bg-[#252526]">
        {['terraform', 'aws'].map((t) => (
          <button key={t} onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm capitalize ${tab === t ? 'border-b-2 border-violet-400 text-white' : 'text-slate-400'}`}>
            {t === 'aws' ? 'AWS CLI' : 'Terraform'}
          </button>
        ))}
      </div>

      <div className="flex-1 flex flex-col min-h-0 p-4 gap-3 overflow-auto">
        {tab === 'terraform' && (
          <>
            <div className="flex flex-wrap gap-2">
              <button onClick={() => run('terraform_init', {}, 'Initialized')} disabled={busy || tf.initialized}
                className="px-3 py-1.5 rounded bg-violet-600 text-sm disabled:opacity-50">terraform init</button>
              <button onClick={() => run('terraform_plan')} disabled={busy || !tf.initialized}
                className="px-3 py-1.5 rounded bg-slate-700 text-sm disabled:opacity-50">terraform plan</button>
              <button onClick={() => run('terraform_apply')} disabled={busy || !tf.last_plan}
                className="px-3 py-1.5 rounded bg-green-700 text-sm disabled:opacity-50 flex items-center gap-1"><Play size={14} /> apply</button>
              {state?.state?.broken?.stale_lock && (
                <button onClick={() => run('force_unlock', {}, 'Lock released')} disabled={busy}
                  className="px-3 py-1.5 rounded bg-amber-700 text-sm">force-unlock</button>
              )}
              <button onClick={refresh} className="px-3 py-1.5 rounded border border-slate-600 text-sm flex items-center gap-1"><RefreshCw size={14} /> refresh</button>
            </div>
            <div className="text-xs text-slate-400">Workspace: {tf.workspace || 'default'} · Drift: {tf.drift_detected ? 'yes' : 'no'}</div>
          </>
        )}
        {tab === 'aws' && (
          <div className="flex gap-2">
            <input value={awsCmd} onChange={(e) => setAwsCmd(e.target.value)} className="flex-1 bg-[#252526] border border-slate-600 rounded px-3 py-2 text-sm font-mono" />
            <button onClick={() => run('aws_cli', { command: awsCmd })} disabled={busy}
              className="px-4 py-2 rounded bg-[#ff9900] text-black text-sm font-medium">Run</button>
          </div>
        )}
        <pre className="flex-1 min-h-[200px] bg-black/50 rounded p-3 text-xs font-mono overflow-auto border border-slate-700">
          {output || <span className="text-slate-500 flex items-center gap-2"><Terminal size={14} /> Output appears here…</span>}
        </pre>
      </div>
    </div>
  )
}
