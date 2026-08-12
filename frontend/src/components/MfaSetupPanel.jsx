import { useCallback, useEffect, useState } from 'react'
import { ShieldCheck, ShieldAlert, Copy, Check, AlertTriangle } from 'lucide-react'
import toast from 'react-hot-toast'
import { authApi } from '../api/auth'

// MFA enrolment (audit Z2-3). The backend endpoints are useless without this —
// there would be no way for anyone to actually turn MFA on.
//
// `qrcode` is imported dynamically. It is only needed on this panel, and the eager
// bundle is already the subject of Z6-7; a static import would put a QR encoder in
// front of every marketing visitor. Manual entry is offered alongside because the
// QR is a convenience, not the mechanism — every authenticator app accepts a typed
// key, and someone setting up on the same device they are reading this on cannot
// scan their own screen.

function chunk(secret) {
  // Grouped into fours: a 32-character base32 string typed by hand is otherwise
  // an invitation to transpose two characters and get an unexplained failure.
  return (secret || '').replace(/(.{4})/g, '$1 ').trim()
}

function CopyButton({ value, label }) {
  const [copied, setCopied] = useState(false)
  return (
    <button
      type="button"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(value)
          setCopied(true)
          setTimeout(() => setCopied(false), 2000)
        } catch {
          toast.error('Could not copy — select the text manually.')
        }
      }}
      className="text-surface-400 hover:text-accent-cyan transition-colors"
      aria-label={label}
    >
      {copied ? <Check size={14} className="text-accent-green" /> : <Copy size={14} />}
    </button>
  )
}

export default function MfaSetupPanel() {
  const [status, setStatus] = useState(null)
  const [enrolling, setEnrolling] = useState(null)   // { secret, provisioning_uri }
  const [qr, setQr] = useState('')
  const [code, setCode] = useState('')
  const [busy, setBusy] = useState(false)
  const [recoveryCodes, setRecoveryCodes] = useState(null)
  const [disablePassword, setDisablePassword] = useState('')

  const refresh = useCallback(() => {
    authApi.mfaStatus().then(setStatus).catch(() => setStatus(null))
  }, [])

  useEffect(() => { refresh() }, [refresh])

  useEffect(() => {
    if (!enrolling?.provisioning_uri) { setQr(''); return }
    let cancelled = false
    import('qrcode')
      .then((m) => (m.default || m).toDataURL(enrolling.provisioning_uri, { margin: 1, width: 200 }))
      .then((url) => { if (!cancelled) setQr(url) })
      // A failed QR render must not block setup — the typed key still works.
      .catch(() => { if (!cancelled) setQr('') })
    return () => { cancelled = true }
  }, [enrolling])

  const startEnrol = async () => {
    setBusy(true)
    try {
      setEnrolling(await authApi.mfaEnroll())
    } catch (err) {
      toast.error(err?.response?.data?.error || 'Could not start setup.')
    } finally {
      setBusy(false)
    }
  }

  const confirm = async (e) => {
    e.preventDefault()
    setBusy(true)
    try {
      const data = await authApi.mfaConfirm(code.trim())
      setRecoveryCodes(data.recovery_codes)
      setEnrolling(null)
      setCode('')
      refresh()
      toast.success('Two-factor authentication is on')
    } catch (err) {
      toast.error(err?.response?.data?.error || 'That code did not work.')
    } finally {
      setBusy(false)
    }
  }

  const disable = async (e) => {
    e.preventDefault()
    setBusy(true)
    try {
      await authApi.mfaDisable(disablePassword, code.trim())
      setDisablePassword('')
      setCode('')
      refresh()
      toast.success('Two-factor authentication turned off')
    } catch (err) {
      toast.error(err?.response?.data?.error || 'Could not turn it off.')
    } finally {
      setBusy(false)
    }
  }

  if (!status) return null

  return (
    <div className="glass-card p-6">
      <h2 className="text-lg font-semibold text-white mb-1 flex items-center gap-2">
        {status.enabled
          ? <ShieldCheck size={18} className="text-accent-green" />
          : <ShieldAlert size={18} className="text-accent-amber" />}
        Two-Factor Authentication
      </h2>
      <p className="text-sm text-surface-400 mb-4">
        {status.enabled
          ? 'Your account asks for a code from your authenticator app at sign-in.'
          : 'Add a second step at sign-in so a stolen password is not enough on its own.'}
      </p>

      {/* Staff cannot switch this off, so saying "required" is more honest than
          offering a disable button that returns 403. */}
      {status.required && !status.enabled && (
        <div className="flex items-start gap-2 bg-accent-amber/10 border border-accent-amber/20 text-accent-amber text-sm p-3 rounded-lg mb-4">
          <AlertTriangle size={16} className="shrink-0 mt-0.5" />
          <span>Two-factor authentication is required for staff accounts. Please set it up now.</span>
        </div>
      )}

      {/* Shown exactly once. Regenerating is the only way to see them again, and
          that invalidates the set below. */}
      {recoveryCodes && (
        <div className="bg-surface-800/60 border border-accent-amber/30 rounded-lg p-4 mb-4">
          <p className="text-sm text-white font-medium mb-1">Save your recovery codes now</p>
          <p className="text-xs text-surface-400 mb-3">
            These are shown once. Each works a single time, and they are the only way
            back in if you lose your phone.
          </p>
          <div className="grid grid-cols-2 gap-1.5 font-mono text-sm text-surface-200 mb-3">
            {recoveryCodes.map((c) => <div key={c}>{c}</div>)}
          </div>
          <div className="flex items-center gap-3">
            <CopyButton value={recoveryCodes.join('\n')} label="Copy recovery codes" />
            <button
              type="button"
              onClick={() => setRecoveryCodes(null)}
              className="text-xs text-surface-400 hover:text-white"
            >
              I have saved them
            </button>
          </div>
        </div>
      )}

      {!status.enabled && !enrolling && (
        <button onClick={startEnrol} disabled={busy} className="btn-primary text-sm px-5 py-2">
          {busy ? 'Starting…' : 'Set up two-factor'}
        </button>
      )}

      {enrolling && (
        <form onSubmit={confirm} className="space-y-4">
          <div className="flex flex-col sm:flex-row gap-4 items-start">
            {qr && (
              <img
                src={qr}
                alt="QR code for your authenticator app"
                className="rounded-lg bg-white p-2 shrink-0"
                width={200}
                height={200}
              />
            )}
            <div className="text-sm text-surface-400 space-y-2">
              <p>Scan this with Google Authenticator, Authy, or 1Password.</p>
              <p className="text-xs">
                Can&apos;t scan? Enter this key manually:
              </p>
              <div className="flex items-center gap-2 font-mono text-xs text-surface-200 bg-surface-800/60 rounded px-2 py-1.5">
                <span className="break-all">{chunk(enrolling.secret)}</span>
                <CopyButton value={enrolling.secret} label="Copy setup key" />
              </div>
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-surface-300 mb-1.5">
              Enter the 6-digit code to finish
            </label>
            <input
              type="text"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              className="input-field max-w-[200px] text-center tracking-[0.3em]"
              placeholder="000000"
              inputMode="numeric"
              maxLength={6}
              autoComplete="one-time-code"
              required
            />
          </div>

          <div className="flex gap-3">
            <button type="submit" disabled={busy || code.trim().length !== 6} className="btn-primary text-sm px-5 py-2">
              {busy ? 'Verifying…' : 'Turn on'}
            </button>
            <button
              type="button"
              onClick={() => { setEnrolling(null); setCode('') }}
              className="btn-secondary text-sm px-5 py-2"
            >
              Cancel
            </button>
          </div>
        </form>
      )}

      {status.enabled && !status.required && (
        <form onSubmit={disable} className="space-y-3 mt-2">
          <p className="text-xs text-surface-500">
            Turning this off needs your password and a current code — disabling
            two-factor is the first thing someone with a stolen session would do.
          </p>
          <div className="flex flex-col sm:flex-row gap-2">
            <input
              type="password"
              value={disablePassword}
              onChange={(e) => setDisablePassword(e.target.value)}
              className="input-field text-sm"
              placeholder="Current password"
              autoComplete="current-password"
              required
            />
            <input
              type="text"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              className="input-field text-sm sm:max-w-[140px] text-center tracking-[0.2em]"
              placeholder="000000"
              inputMode="numeric"
              maxLength={6}
              autoComplete="one-time-code"
              required
            />
            <button type="submit" disabled={busy} className="btn-danger text-sm px-4 py-2 whitespace-nowrap">
              Turn off
            </button>
          </div>
        </form>
      )}

      {status.enabled && status.recovery_codes_remaining <= 2 && (
        <p className="text-xs text-accent-amber mt-3 flex items-center gap-1.5">
          <AlertTriangle size={12} />
          Only {status.recovery_codes_remaining} recovery codes left.
        </p>
      )}
    </div>
  )
}
