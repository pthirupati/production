import { useState } from 'react'
import { Link } from 'react-router-dom'

const ROLES = [
  { id: 'Administrator', label: 'Administrator — full access' },
  { id: 'Virtual Machine Administrator', label: 'VM Administrator' },
  { id: 'Virtual Machine User', label: 'VM User — power ops only' },
  { id: 'Read Only', label: 'Read Only' },
  { id: 'Network Administrator', label: 'Network Administrator' },
  { id: 'Storage Administrator', label: 'Storage Administrator' },
]

const VCENTER_USER = 'lab_vmware'
const VCENTER_PASS = 'lab_vmware@123'
const STORAGE_KEY = 'fixitlab_vcenter_auth'
const ROLE_KEY = 'fixitlab_vcenter_role'

export function isVcenterAuthenticated() {
  try {
    return sessionStorage.getItem(STORAGE_KEY) === '1'
  } catch {
    return false
  }
}

export function getVcenterRole() {
  try {
    return sessionStorage.getItem(ROLE_KEY) || 'Administrator'
  } catch {
    return 'Administrator'
  }
}

export function setVcenterAuthenticated(role = 'Administrator') {
  try {
    sessionStorage.setItem(STORAGE_KEY, '1')
    sessionStorage.setItem(ROLE_KEY, role)
  } catch { /* ignore */ }
}

export function clearVcenterAuth() {
  try {
    sessionStorage.removeItem(STORAGE_KEY)
    sessionStorage.removeItem(ROLE_KEY)
  } catch { /* ignore */ }
}

/* Real vSphere SSO login: split panel, "VMware vSphere" title, domain\username
   field, password, "Use Windows session authentication" checkbox, full-width
   LOGIN button. Keeps the lab_vmware autofill + hint. */
export default function VmwareLoginGate({ onAuthenticated, backTo }) {
  const [user, setUser] = useState('')
  const [pass, setPass] = useState('')
  const [role, setRole] = useState('Administrator')
  const [winSession, setWinSession] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  // vSphere accepts both bare "lab_vmware" and "vsphere.local\lab_vmware".
  const normalize = (u) => (u || '').includes('\\') ? u.split('\\').pop() : u

  const submit = (e) => {
    e.preventDefault()
    setLoading(true)
    setError('')
    setTimeout(() => {
      if (normalize(user) === VCENTER_USER && pass === VCENTER_PASS) {
        setVcenterAuthenticated(role)
        onAuthenticated(role)
      } else {
        setError('Invalid credentials. Use lab_vmware / lab_vmware@123 for training labs.')
      }
      setLoading(false)
    }, 400)
  }

  return (
    <div className="vmware-sim min-h-screen flex items-stretch bg-[#0f1722]">
      {/* ── Left brand panel ── */}
      <div className="hidden md:flex md:w-1/2 lg:w-3/5 flex-col justify-between p-12 bg-gradient-to-br from-[#0a1d3d] via-[#10243f] to-[#0f1722] relative overflow-hidden">
        <div
          aria-hidden
          className="absolute inset-0 opacity-[0.18]"
          style={{ background: 'radial-gradient(900px 500px at 18% 22%, #2d7cff55, transparent 60%), radial-gradient(700px 400px at 80% 80%, #00c8ff44, transparent 55%)' }}
        />
        <div className="relative">
          <div className="text-3xl font-bold text-white tracking-tight">
            <span className="text-[#5b9bf5]">vm</span>ware
          </div>
        </div>
        <div className="relative">
          <h1 className="text-[44px] leading-[1.05] font-light text-white mb-3">
            VMware<br /><span className="font-semibold">vSphere</span>
          </h1>
          <p className="text-[#9fb6cc] text-sm max-w-md leading-relaxed">
            The vSphere Client manages your virtual datacenter — hosts, clusters,
            virtual machines, storage and networking — from a single console.
          </p>
        </div>
        <div className="relative text-[11px] text-[#5d7a93]">
          vCenter Server Appliance 7.0.3 · build 20328353 · FixitLab training environment
        </div>
      </div>

      {/* ── Right login panel ── */}
      <div className="w-full md:w-1/2 lg:w-2/5 flex items-center justify-center p-6 bg-[#101d2c] border-l border-[#1f2f42]">
        <div className="w-full max-w-sm">
          <div className="md:hidden text-2xl font-bold text-white mb-6 text-center">
            <span className="text-[#5b9bf5]">vm</span>ware <span className="text-[#8fa5b8] text-base font-normal">vSphere</span>
          </div>
          <h2 className="text-xl font-semibold text-white mb-1">Sign in</h2>
          <p className="text-xs text-[#8fa5b8] mb-6">vSphere Single Sign-On (vsphere.local)</p>

          <form onSubmit={submit} className="space-y-4">
            <div>
              <label className="block text-[11px] text-[#8fa5b8] mb-1.5 uppercase tracking-wide">Username</label>
              <input
                value={user}
                onChange={e => setUser(e.target.value)}
                disabled={winSession}
                className="vm-input !pl-3 w-full disabled:opacity-50"
                autoComplete="username"
                placeholder="vsphere.local\lab_vmware"
              />
            </div>
            <div>
              <label className="block text-[11px] text-[#8fa5b8] mb-1.5 uppercase tracking-wide">Password</label>
              <input
                type="password"
                value={pass}
                onChange={e => setPass(e.target.value)}
                disabled={winSession}
                className="vm-input !pl-3 w-full disabled:opacity-50"
                autoComplete="current-password"
              />
            </div>
            <div>
              <label className="block text-[11px] text-[#8fa5b8] mb-1.5 uppercase tracking-wide">Role (RBAC)</label>
              <select value={role} onChange={e => setRole(e.target.value)} className="vm-input !pl-3 w-full">
                {ROLES.map(r => <option key={r.id} value={r.id}>{r.label}</option>)}
              </select>
            </div>
            <label className="flex items-center gap-2 text-xs text-[#c3d3e3] cursor-pointer select-none">
              <input
                type="checkbox"
                checked={winSession}
                onChange={e => { setWinSession(e.target.checked); if (e.target.checked) { setUser(VCENTER_USER); setPass(VCENTER_PASS); setError('') } }}
              />
              Use Windows session authentication
            </label>
            {error && <p className="text-xs text-[#f08080] bg-[rgba(217,83,79,.12)] border border-[rgba(217,83,79,.3)] rounded px-3 py-2">{error}</p>}
            <button type="submit" disabled={loading} className="vm-btn vm-btn-blue w-full justify-center py-2.5 text-sm font-bold uppercase tracking-wide">
              {loading ? 'Signing in…' : 'Login'}
            </button>
            <button
              type="button"
              onClick={() => { setWinSession(false); setUser(VCENTER_USER); setPass(VCENTER_PASS); setError('') }}
              className="vm-btn w-full justify-center py-2 text-xs"
            >
              Use lab credentials (autofill)
            </button>
          </form>

          {backTo ? (
            <Link
              to={backTo}
              className="block mt-4 text-center text-[#5aa3ff] text-xs hover:underline"
            >
              ← Back to lab
            </Link>
          ) : null}

          <p className="text-[10px] text-[#8fa5b8] text-center leading-relaxed mt-5 pt-4 border-t border-[#1f2f42]">
            Training credentials:{' '}
            <span className="font-mono text-[#E8EDF2]">lab_vmware</span> /{' '}
            <span className="font-mono text-[#E8EDF2]">lab_vmware@123</span>
          </p>
        </div>
      </div>
    </div>
  )
}
