import { useState } from 'react'
import { ChevronRight, CheckCircle2 } from 'lucide-react'

const STEPS = [
  { id: 'begin', label: 'Before You Begin' },
  { id: 'type', label: 'Installation Type' },
  { id: 'server', label: 'Server Selection' },
  { id: 'roles', label: 'Server Roles' },
  { id: 'features', label: 'Features' },
  { id: 'confirm', label: 'Confirmation' },
  { id: 'results', label: 'Results' },
]

const ROLE_TREE = [
  { id: 'AD-Domain-Services', label: 'Active Directory Domain Services', category: 'role' },
  { id: 'DNS', label: 'DNS Server', category: 'role' },
  { id: 'DHCP', label: 'DHCP Server', category: 'role' },
  { id: 'Web-Server', label: 'Web Server (IIS)', category: 'role', children: ['Web Server', 'FTP Server', 'Management Tools'] },
  { id: 'Hyper-V', label: 'Hyper-V', category: 'role' },
  { id: 'File-Storage', label: 'File and Storage Services', category: 'role', children: ['File Server', 'iSCSI Target Server'] },
  { id: 'Remote-Desktop', label: 'Remote Desktop Services', category: 'role' },
  { id: 'WSUS', label: 'Windows Server Update Services', category: 'role' },
]

export default function AddRolesWizard({ open, onClose, installable = [], roles = [], computerName, busy, onInstall }) {
  const [step, setStep] = useState(0)
  const [installType, setInstallType] = useState('role')
  const [selectedRoles, setSelectedRoles] = useState([])
  const [selectedFeatures, setSelectedFeatures] = useState([])
  const [result, setResult] = useState(null)

  if (!open) return null

  const toggleRole = (id) => {
    setSelectedRoles((prev) => prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id])
  }

  const handleNext = async () => {
    if (STEPS[step].id === 'confirm') {
      const roleId = selectedRoles[0] || installable[0]?.id
      if (roleId && onInstall) {
        await onInstall(roleId)
        setResult({ success: true, role: roles.find((r) => r.id === roleId)?.name || roleId })
      }
      setStep((s) => s + 1)
      return
    }
    if (step < STEPS.length - 1) setStep((s) => s + 1)
    else onClose?.()
  }

  const handleClose = () => {
    setStep(0)
    setSelectedRoles([])
    setResult(null)
    onClose?.()
  }

  const s = STEPS[step]

  return (
    <div className="win-dialog-backdrop" onClick={handleClose}>
      <div className="win-dialog !max-w-3xl !w-[95vw]" onClick={(e) => e.stopPropagation()}>
        <div className="win-dialog-head flex items-center justify-between">
          <span>Add Roles and Features Wizard</span>
          <span className="text-xs opacity-80">Step {step + 1} of {STEPS.length}</span>
        </div>
        <div className="flex min-h-[360px]">
          <nav className="w-44 shrink-0 bg-[#f3f3f3] border-r border-[#e1e1e1] p-2 text-xs">
            {STEPS.map((st, i) => (
              <div key={st.id} className={`flex items-center gap-1.5 py-1.5 px-2 rounded ${i === step ? 'bg-white font-semibold text-[#0078D4]' : i < step ? 'text-[#107c10]' : 'text-[#616161]'}`}>
                {i < step ? <CheckCircle2 size={12} /> : <span className="w-3 text-center">{i + 1}</span>}
                {st.label}
              </div>
            ))}
          </nav>
          <div className="win-dialog-body flex-1 overflow-y-auto">
            {s.id === 'begin' && (
              <div className="space-y-3 text-sm">
                <p>This wizard helps you install roles, role services, or features on <strong>{computerName}</strong>.</p>
                <ul className="list-disc pl-5 text-[#616161] space-y-1">
                  <li>Roles provide the primary functionality of Windows Server</li>
                  <li>Features provide additional functionality or support for roles</li>
                  <li>Some roles require other roles or features to be installed first</li>
                </ul>
              </div>
            )}
            {s.id === 'type' && (
              <div className="space-y-2 text-sm">
                <label className="flex items-center gap-2 p-3 border rounded cursor-pointer hover:bg-[#f7fbff]">
                  <input type="radio" checked={installType === 'role'} onChange={() => setInstallType('role')} />
                  Role-based or feature-based installation
                </label>
                <label className="flex items-center gap-2 p-3 border rounded cursor-pointer hover:bg-[#f7fbff] opacity-60">
                  <input type="radio" disabled />
                  Remote Desktop Services installation (disabled in lab)
                </label>
              </div>
            )}
            {s.id === 'server' && (
              <div className="text-sm">
                <p className="mb-2 text-[#616161]">Select the destination server:</p>
                <div className="border rounded p-3 bg-[#f7fbff] font-medium flex items-center gap-2">
                  <CheckCircle2 size={16} className="text-[#107c10]" /> {computerName} (local server)
                </div>
              </div>
            )}
            {s.id === 'roles' && (
              <div className="text-sm max-h-[280px] overflow-y-auto border rounded p-2">
                {ROLE_TREE.map((r) => {
                  const available = installable.some((i) => i.id === r.id) || !roles.find((x) => x.id === r.id)?.installed
                  const checked = selectedRoles.includes(r.id)
                  return (
                    <div key={r.id} className="py-1">
                      <label className={`flex items-center gap-2 py-1 ${available ? 'cursor-pointer hover:bg-[#f7fbff]' : 'opacity-50'}`}>
                        <input type="checkbox" disabled={!available} checked={checked} onChange={() => toggleRole(r.id)} />
                        <span className="font-medium">{r.label}</span>
                      </label>
                      {r.children?.map((c) => (
                        <label key={c} className="flex items-center gap-2 pl-6 py-0.5 text-[#616161] cursor-pointer">
                          <input type="checkbox" checked={selectedFeatures.includes(c)} onChange={() => setSelectedFeatures((p) => p.includes(c) ? p.filter((x) => x !== c) : [...p, c])} />
                          {c}
                        </label>
                      ))}
                    </div>
                  )
                })}
              </div>
            )}
            {s.id === 'features' && (
              <p className="text-sm text-[#616161]">No additional features required for the selected roles. Click Next to continue.</p>
            )}
            {s.id === 'confirm' && (
              <div className="text-sm space-y-2">
                <p>Ready to install the following on <strong>{computerName}</strong>:</p>
                <ul className="list-disc pl-5">
                  {selectedRoles.map((id) => <li key={id}>{roles.find((r) => r.id === id)?.name || id}</li>)}
                  {selectedRoles.length === 0 && installable[0] && <li>{installable[0].name}</li>}
                </ul>
              </div>
            )}
            {s.id === 'results' && (
              <div className="text-sm text-center py-6">
                {result?.success ? (
                  <>
                    <CheckCircle2 size={40} className="mx-auto text-[#107c10] mb-3" />
                    <p className="font-semibold text-lg">Installation succeeded</p>
                    <p className="text-[#616161] mt-1">{result.role} was installed successfully.</p>
                  </>
                ) : (
                  <p>Installation complete.</p>
                )}
              </div>
            )}
          </div>
        </div>
        <div className="win-dialog-foot">
          {step > 0 && step < STEPS.length - 1 && (
            <button type="button" className="win-light-btn mr-auto" onClick={() => setStep((s) => s - 1)}>Back</button>
          )}
          <button type="button" className="win-light-btn" onClick={handleClose}>{step === STEPS.length - 1 ? 'Close' : 'Cancel'}</button>
          {step < STEPS.length - 1 && (
            <button type="button" className="win-light-btn win-primary !text-white flex items-center gap-1" disabled={busy} onClick={handleNext}>
              {s.id === 'confirm' ? 'Install' : 'Next'} <ChevronRight size={14} />
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
