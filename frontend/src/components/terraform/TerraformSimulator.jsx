import { useState } from 'react'
import { terraformApi } from '../../api/terraform'
import LabChromeBar from '../lab/LabChromeBar'
import { Cloud, LogIn, AlertTriangle, RefreshCw } from 'lucide-react'
import { simPanelRoot } from '../../utils/simLayout'
import { getIacProfile } from '../../utils/iacFlavor'
import { useSimSession } from '../sim/shared'
import TerraformCloudShell from './TerraformCloudShell'
import '../../styles/lab-chrome.css'
import '../../styles/sim-products.css'

const TFC_LAB_USER = 'lab_terraform'
const TFC_LAB_PASS = 'lab_terraform@123'
const TFC_AUTH_KEY = 'fixitlab_terraform_auth'

function isTerraformAuthed() {
  try {
    return sessionStorage.getItem(TFC_AUTH_KEY) === '1'
  } catch {
    return false
  }
}

export default function TerraformSimulator(props) {
  const {
    sessionId, scenario, embedded = false,
    terminalSession, terminalHost, blockedCommands, isMobile,
    onExit, onStop, onHints, onCheck, onExtend, hintsLabel, checkDisabled, extendDisabled,
    onToggleTerminal, simTerminalOpen, vmwareHref = null,
  } = props
  const slug = scenario?.slug || ''
  const iac = getIacProfile()
  const { state, setState, loading, busy, error, refresh, run } = useSimSession(sessionId, slug, terraformApi)
  const [authenticated, setAuthenticated] = useState(isTerraformAuthed)
  const [loginUser, setLoginUser] = useState('')
  const [loginPass, setLoginPass] = useState('')
  const [loginError, setLoginError] = useState('')

  const chromeProps = {
    onHints, onCheck, onExtend, onStop,
    onBackToTerminal: onExit || onToggleTerminal,
    hintsLabel, checkDisabled, extendDisabled,
    backLabel: simTerminalOpen ? 'Hide terminal' : (onExit ? 'Close' : 'Terminal'),
    vmwareHref,
  }

  if (loading) {
    return (
      <div className={simPanelRoot(embedded, 'tfc-shell flex items-center justify-center text-slate-400')}>
        <LabChromeBar icon={Cloud} title={iac.cloudTitle} subtitle={slug} accent={iac.accent} {...chromeProps} />
        <p className="p-8 text-sm">Loading {iac.label} workspace…</p>
      </div>
    )
  }

  if (error || !state) {
    return (
      <div className={simPanelRoot(embedded, 'tfc-shell flex flex-col bg-[#1e1e1e]')}>
        <LabChromeBar icon={Cloud} title={iac.cloudTitle} subtitle={scenario?.title || slug} accent={iac.accent} {...chromeProps} />
        <div className="flex-1 flex flex-col items-center justify-center gap-3 p-6 text-center">
          <AlertTriangle className="text-amber-400" size={32} aria-hidden />
          <p className="text-sm text-slate-300 max-w-md">
            {error || `Could not load ${iac.label} state. Check that the lab session is running, then retry.`}
          </p>
          <button
            type="button"
            onClick={() => refresh()}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-violet-500/40 text-violet-300 text-sm hover:bg-violet-500/10"
          >
            <RefreshCw size={14} /> Retry
          </button>
        </div>
      </div>
    )
  }

  if (!authenticated) {
    const submitLogin = (e) => {
      e.preventDefault()
      const ok = loginUser.trim().toLowerCase() === TFC_LAB_USER && loginPass === TFC_LAB_PASS
      if (ok) {
        try { sessionStorage.setItem(TFC_AUTH_KEY, '1') } catch { /* ignore */ }
        setLoginError('')
        setAuthenticated(true)
      } else {
        setLoginError(`Invalid credentials. Use ${TFC_LAB_USER} / ${TFC_LAB_PASS} for training labs.`)
      }
    }

    return (
      <div className={simPanelRoot(embedded, 'tfc-shell flex flex-col bg-[#f7f7f7]')}>
        <LabChromeBar icon={Cloud} title={iac.cloudTitle} subtitle={scenario?.title || slug} accent={iac.accent} {...chromeProps} />
        <div className="flex-1 flex items-center justify-center p-6">
          <div className="w-full max-w-sm rounded-xl border border-slate-200 bg-white shadow-2xl overflow-hidden">
            <div className="px-6 py-4 text-white font-semibold flex items-center gap-2" style={{ background: iac.accent || '#5c4ee5' }}>
              <Cloud size={18} /> {iac.cloudTitle}
            </div>
            <form onSubmit={submitLogin} className="p-6 space-y-4">
              <p className="text-sm text-slate-600">Sign in to the Terraform Cloud training organization.</p>
              <div>
                <label className="block text-[11px] font-semibold uppercase tracking-wide text-slate-500 mb-1">Username</label>
                <input value={loginUser} onChange={(e) => setLoginUser(e.target.value)} autoFocus autoComplete="username"
                  placeholder={TFC_LAB_USER}
                  className="w-full border border-slate-300 rounded px-3 py-2 text-sm focus:outline-none focus:border-[#5c4ee5]" />
              </div>
              <div>
                <label className="block text-[11px] font-semibold uppercase tracking-wide text-slate-500 mb-1">Password</label>
                <input type="password" value={loginPass} onChange={(e) => setLoginPass(e.target.value)} autoComplete="current-password"
                  className="w-full border border-slate-300 rounded px-3 py-2 text-sm focus:outline-none focus:border-[#5c4ee5]" />
              </div>
              {loginError && <p className="text-xs text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2">{loginError}</p>}
              <button type="submit" className="w-full py-2 rounded text-white font-semibold flex items-center justify-center gap-2" style={{ background: iac.accent || '#5c4ee5' }}>
                <LogIn size={16} /> Sign In
              </button>
              <button type="button"
                onClick={() => { setLoginUser(TFC_LAB_USER); setLoginPass(TFC_LAB_PASS); setLoginError('') }}
                className="w-full py-1.5 text-xs text-slate-600 border border-slate-300 rounded hover:bg-slate-50">
                Use lab credentials (autofill)
              </button>
              <p className="text-[10px] text-slate-500 text-center pt-2 border-t border-slate-100">
                Training credentials: <span className="font-mono text-slate-700">{TFC_LAB_USER}</span> / <span className="font-mono text-slate-700">{TFC_LAB_PASS}</span>
              </p>
            </form>
          </div>
        </div>
      </div>
    )
  }

  return (
    <TerraformCloudShell
      sessionId={sessionId}
      scenario={scenario}
      embedded={embedded}
      chromeProps={chromeProps}
      terminalSession={terminalSession}
      terminalHost={terminalHost}
      blockedCommands={blockedCommands}
      isMobile={isMobile}
      state={state}
      setState={setState}
      refresh={refresh}
      busy={busy}
      run={run}
      onToggleTerminal={onToggleTerminal}
      simTerminalOpen={simTerminalOpen}
    />
  )
}
