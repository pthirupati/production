import { useState } from 'react'
import { ChevronLeft, ChevronRight, UserPlus } from 'lucide-react'

const STEPS = ['Names', 'Password', 'Groups', 'Profile', 'Review']

export default function NewUserWizard({ open, onClose, ous = ['Users'], busy, onCreate }) {
  const [step, setStep] = useState(0)
  const [form, setForm] = useState({
    firstName: '', lastName: '', sam: '', upn: '', ou: ous[0] || 'Users',
    password: '', mustChange: true, groups: ['Domain Users'],
  })

  if (!open) return null
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }))

  const finish = () => {
    const name = (form.sam || `${form.firstName}.${form.lastName}`.toLowerCase()).replace(/\s+/g, '')
    onCreate?.({
      name,
      display: `${form.firstName} ${form.lastName}`.trim() || name,
      ou: form.ou,
      group: form.groups[0] || 'Domain Users',
      groups: form.groups.length ? form.groups : ['Domain Users'],
      must_change_pw: form.mustChange,
    })
    onClose?.()
    setStep(0)
    setForm({
      firstName: '', lastName: '', sam: '', upn: '', ou: ous[0] || 'Users',
      password: '', mustChange: true, groups: ['Domain Users'],
    })
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="bg-white rounded shadow-2xl w-full max-w-lg overflow-hidden border border-[var(--win-border,#e1e1e1)]">
        <div className="px-4 py-3 bg-[#0078D4] text-white flex items-center gap-2">
          <UserPlus size={18} />
          <span className="font-semibold">New Object — User</span>
        </div>
        <div className="px-4 py-2 bg-[#f3f3f3] border-b flex gap-1 overflow-x-auto">
          {STEPS.map((s, i) => (
            <span key={s} className={`text-[10px] px-2 py-1 rounded ${i === step ? 'bg-[#0078D4] text-white' : 'text-[#616161]'}`}>{i + 1}. {s}</span>
          ))}
        </div>
        <div className="p-5 space-y-3 text-sm min-h-[220px]">
          {step === 0 && (
            <>
              <label className="block">First name<input className="win-input w-full mt-1" value={form.firstName} onChange={(e) => set('firstName', e.target.value)} /></label>
              <label className="block">Last name<input className="win-input w-full mt-1" value={form.lastName} onChange={(e) => set('lastName', e.target.value)} /></label>
              <label className="block">User logon name (pre-Windows 2000)<input className="win-input w-full mt-1 font-mono" value={form.sam} onChange={(e) => set('sam', e.target.value)} placeholder="jsmith" /></label>
              <label className="block">OU
                <select className="win-input w-full mt-1" value={form.ou} onChange={(e) => set('ou', e.target.value)}>
                  {ous.map((o) => <option key={o} value={o}>{o}</option>)}
                </select>
              </label>
            </>
          )}
          {step === 1 && (
            <>
              <label className="block">Password<input type="password" className="win-input w-full mt-1" value={form.password} onChange={(e) => set('password', e.target.value)} /></label>
              <label className="flex items-center gap-2 text-xs"><input type="checkbox" checked={form.mustChange} onChange={(e) => set('mustChange', e.target.checked)} /> User must change password at next logon</label>
            </>
          )}
          {step === 2 && (
            <div className="space-y-1">
              {['Domain Users', 'Remote Desktop Users', 'DNSAdmins'].map((g) => (
                <label key={g} className="flex items-center gap-2 text-xs py-1">
                  <input type="checkbox" checked={form.groups.includes(g)} onChange={(e) => set('groups', e.target.checked ? [...form.groups, g] : form.groups.filter((x) => x !== g))} />
                  {g}
                </label>
              ))}
            </div>
          )}
          {step === 3 && (
            <p className="text-[#616161] text-xs">Profile path, logon script, and home folder can be configured after creation in the user Properties dialog.</p>
          )}
          {step === 4 && (
            <div className="text-xs space-y-1 font-mono bg-[#f9f9f9] p-3 rounded border">
              <div>CN: {form.firstName} {form.lastName}</div>
              <div>sAMAccountName: {form.sam || '—'}</div>
              <div>OU: {form.ou}</div>
              <div>Groups: {form.groups.join(', ')}</div>
            </div>
          )}
        </div>
        <div className="px-4 py-3 border-t flex justify-between bg-[#fafafa]">
          <button type="button" className="win-light-btn" disabled={step === 0} onClick={() => setStep((s) => s - 1)}><ChevronLeft size={14} /> Back</button>
          <button type="button" className="win-light-btn" onClick={onClose}>Cancel</button>
          {step < STEPS.length - 1 ? (
            <button type="button" className="win-light-btn win-primary !text-white" onClick={() => setStep((s) => s + 1)}>Next <ChevronRight size={14} /></button>
          ) : (
            <button type="button" className="win-light-btn win-primary !text-white" disabled={busy} onClick={finish}>Create</button>
          )}
        </div>
      </div>
    </div>
  )
}
