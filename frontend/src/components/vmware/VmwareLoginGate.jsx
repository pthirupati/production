import { useState } from 'react'

const VCENTER_USER = 'lab_vmware'
const VCENTER_PASS = 'lab_vmware@123'
const STORAGE_KEY = 'fixitlab_vcenter_auth'

export function isVcenterAuthenticated() {
  try {
    return sessionStorage.getItem(STORAGE_KEY) === '1'
  } catch {
    return false
  }
}

export function setVcenterAuthenticated() {
  try {
    sessionStorage.setItem(STORAGE_KEY, '1')
  } catch { /* ignore */ }
}

export function clearVcenterAuth() {
  try {
    sessionStorage.removeItem(STORAGE_KEY)
  } catch { /* ignore */ }
}

export default function VmwareLoginGate({ onAuthenticated }) {
  const [user, setUser] = useState('')
  const [pass, setPass] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const submit = (e) => {
    e.preventDefault()
    setLoading(true)
    setError('')
    setTimeout(() => {
      if (user === VCENTER_USER && pass === VCENTER_PASS) {
        setVcenterAuthenticated()
        onAuthenticated()
      } else {
        setError('Invalid credentials. Use lab_vmware / lab_vmware@123 for training labs.')
      }
      setLoading(false)
    }, 400)
  }

  return (
    <div className="vmware-sim min-h-screen flex items-center justify-center bg-[#0f1722] p-6">
      <div className="w-full max-w-md rounded-xl border border-[#2d3a4a] bg-[#1b2a3b] shadow-2xl overflow-hidden">
        <div className="px-6 py-8 text-center border-b border-[#2d3a4a] bg-gradient-to-b from-[#243447] to-[#1b2a3b]">
          <div className="text-2xl font-bold text-white mb-1"><span className="text-[#5b9bf5]">vm</span>ware</div>
          <div className="text-xs text-[#8fa5b8] tracking-widest uppercase">vSphere Client</div>
        </div>
        <form onSubmit={submit} className="p-6 space-y-4">
          <div>
            <label className="block text-[11px] text-[#8fa5b8] mb-1.5 uppercase tracking-wide">Username</label>
            <input value={user} onChange={e => setUser(e.target.value)} className="vm-input !pl-3 w-full" autoComplete="username" placeholder="lab_vmware" />
          </div>
          <div>
            <label className="block text-[11px] text-[#8fa5b8] mb-1.5 uppercase tracking-wide">Password</label>
            <input type="password" value={pass} onChange={e => setPass(e.target.value)} className="vm-input !pl-3 w-full" autoComplete="current-password" />
          </div>
          {error && <p className="text-xs text-[#D9534F]">{error}</p>}
          <button type="submit" disabled={loading} className="vm-btn vm-btn-blue w-full justify-center py-2.5 text-sm font-semibold">
            {loading ? 'Signing in…' : 'Login'}
          </button>
          <p className="text-[10px] text-[#8fa5b8] text-center leading-relaxed">
            Training credentials: <span className="font-mono text-[#E8EDF2]">lab_vmware</span> / <span className="font-mono text-[#E8EDF2]">lab_vmware@123</span>
          </p>
        </form>
      </div>
    </div>
  )
}
