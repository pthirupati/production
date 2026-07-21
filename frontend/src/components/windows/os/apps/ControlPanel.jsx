import { useState } from 'react'
import { Shield, Network, Monitor, Package, Users, Clock, ArrowLeft, RefreshCw, Trash2 } from 'lucide-react'
import { useOS } from '../store'
import { Dialog } from '../ui'

export default function ControlPanel() {
  const os = useOS()
  const [view, setView] = useState('home')
  const [confirm, setConfirm] = useState(null)
  const [updChecking, setUpdChecking] = useState(false)
  const [updBusy, setUpdBusy] = useState('')

  const pendingUpdates = os.updates.filter((u) => {
    const st = String(u.status || '')
    return st.includes('Pending') || st.includes('Failed') || st.includes('Downloading')
  })
  const upToDate = pendingUpdates.length === 0

  const checkUpdates = async () => {
    setUpdChecking(true)
    try {
      if (os.labAction) await os.labAction('check_updates', {})
    } finally {
      setTimeout(() => setUpdChecking(false), 900)
    }
  }

  const installUpdate = async (u) => {
    if (!os.labAction || updBusy) return
    const failed = String(u.status || '').includes('Failed')
    setUpdBusy(u.kb)
    try {
      await os.labAction(failed ? 'retry_update' : 'install_update', { kb: u.kb })
      os.setUpdateStatus(u.kb, 'Successfully installed')
    } finally {
      setUpdBusy('')
    }
  }

  const cats = [
    { id: 'sys', label: 'System and Security', icon: <Shield size={26} color="#107c10" />, sub: 'Review your computer\'s status · Windows Update · Firewall' },
    { id: 'net', label: 'Network and Internet', icon: <Network size={26} color="#0078d4" />, sub: 'View network status and tasks' },
    { id: 'hw', label: 'Hardware and Sound', icon: <Monitor size={26} color="#9b59b6" />, sub: 'Devices and Printers · Power Options · Sound' },
    { id: 'prog', label: 'Programs', icon: <Package size={26} color="#e67e22" />, sub: 'Uninstall a program · Windows features' },
    { id: 'user', label: 'User Accounts', icon: <Users size={26} color="#16a085" />, sub: 'Change account type · Credential Manager' },
    { id: 'clock', label: 'Clock and Region', icon: <Clock size={26} color="#c0392b" />, sub: 'Date and Time · Region' },
  ]

  return (
    <div className="winos-app">
      <div className="winos-toolbar">
        <button className="winos-btn" disabled={view === 'home'} onClick={() => setView('home')}><ArrowLeft size={14} /></button>
        <span style={{ fontSize: 12, color: '#666' }}>Control Panel{view !== 'home' ? ` › ${cats.find((c) => c.id === view)?.label || ''}` : ''}</span>
      </div>
      <div className="winos-main" style={{ padding: 18 }}>
        {view === 'home' && (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 22 }}>
            {cats.map((c) => (
              <div key={c.id} style={{ display: 'flex', gap: 12, cursor: 'default' }} onClick={() => setView(c.id)}>
                {c.icon}
                <div><div style={{ color: '#06c', fontSize: 13 }}>{c.label}</div><div style={{ color: '#666', fontSize: 11.5 }}>{c.sub}</div></div>
              </div>
            ))}
          </div>
        )}

        {view === 'sys' && (
          <div>
            <Section title="Windows Update">
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <RefreshCw size={20} className={updChecking ? 'spin' : ''} color={upToDate ? '#107c10' : '#9d5d00'} />
                <div>
                  <div style={{ fontWeight: 600 }}>
                    {updChecking ? 'Checking for updates…' : (upToDate ? "You're up to date" : `${pendingUpdates.length} update(s) available`)}
                  </div>
                  <div style={{ color: '#666', fontSize: 11.5 }}>Last checked: Today</div>
                </div>
                <span style={{ flex: 1 }} />
                <button type="button" className="winos-btn primary" disabled={updChecking} onClick={checkUpdates}>Check for updates</button>
              </div>
              <div style={{ marginTop: 12, fontWeight: 600, fontSize: 12 }}>Update history</div>
              <table className="winos-table" style={{ marginTop: 4 }}>
                <thead><tr><th>Date</th><th>KB</th><th>Title</th><th>Status</th><th /></tr></thead>
                <tbody>{os.updates.map((u) => {
                  const failed = String(u.status || '').includes('Failed')
                  const pending = String(u.status || '').includes('Pending') || String(u.status || '').includes('Downloading')
                  const ok = String(u.status || '').includes('Success') || String(u.status || '').toLowerCase().includes('installed')
                  return (
                    <tr key={u.kb}>
                      <td>{u.date}</td>
                      <td>{u.kb}</td>
                      <td style={{ maxWidth: 360, overflow: 'hidden', textOverflow: 'ellipsis' }}>{u.title}</td>
                      <td>
                        <span className={`winos-badge ${ok ? 'ok' : failed ? 'err' : 'warn'}`}>{u.status}</span>
                      </td>
                      <td>
                        {(failed || pending) && (
                          <button type="button" className="winos-btn" disabled={!!updBusy || !os.labAction}
                            onClick={() => installUpdate(u)}>
                            {updBusy === u.kb ? '…' : (failed ? 'Retry' : 'Install')}
                          </button>
                        )}
                      </td>
                    </tr>
                  )
                })}</tbody>
              </table>
            </Section>
            <Section title="System">
              <div className="winos-grid2">
                <span style={{ color: '#666' }}>Edition</span><span>{os.computer.edition}</span>
                <span style={{ color: '#666' }}>Computer name</span><span>{os.computer.name}</span>
                <span style={{ color: '#666' }}>Full computer name</span><span>{os.computer.fqdn}</span>
                <span style={{ color: '#666' }}>Domain</span>
                <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                  <span>{os.computer.domain}</span>
                  {os.labAction && (
                    <button type="button" className="winos-btn" onClick={async () => {
                      const domain = window.prompt('Domain to join', os.computer.domain || 'lab.local')
                      if (!domain?.trim()) return
                      await os.labAction('join_domain', { domain: domain.trim() })
                    }}>Change…</button>
                  )}
                </div>
                <span style={{ color: '#666' }}>Processor</span><span>{os.computer.cpu}</span>
                <span style={{ color: '#666' }}>Installed RAM</span><span>{os.computer.ramGB}.0 GB</span>
                <span style={{ color: '#666' }}>System type</span><span>64-bit operating system, x64-based processor</span>
                <span style={{ color: '#666' }}>Activation</span><span style={{ color: '#107c10' }}>Windows is activated</span>
              </div>
            </Section>
            <Section title="Windows Defender Firewall">
              {['Domain', 'Private', 'Public'].map((p) => (
                <div key={p} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '3px 0' }}>
                  <Shield size={16} color="#107c10" /><b>{p} networks</b><span style={{ flex: 1 }} /><span style={{ color: '#107c10' }}>Connected · Firewall On</span>
                </div>
              ))}
            </Section>
          </div>
        )}

        {view === 'prog' && (
          <Section title="Programs and Features">
            <div style={{ color: '#666', fontSize: 12, marginBottom: 6 }}>Uninstall or change a program — select a program and then click Uninstall.</div>
            <table className="winos-table">
              <thead><tr><th>Name</th><th>Publisher</th><th>Installed On</th><th>Size</th><th>Version</th><th></th></tr></thead>
              <tbody>{os.programs.map((p) => (
                <tr key={p.name}><td>{p.name}</td><td>{p.publisher}</td><td>{p.installed}</td><td>{p.size}</td><td>{p.version}</td>
                  <td><button className="winos-btn" onClick={() => setConfirm(p)}><Trash2 size={12} /> Uninstall</button></td></tr>
              ))}</tbody>
            </table>
          </Section>
        )}

        {view === 'net' && (
          <Section title="Network and Sharing Center">
            <div style={{ marginBottom: 10, fontSize: 12.5 }}>View your active networks:</div>
            <div className="winos-card" style={{ padding: 12, marginBottom: 12 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}><b>lab.local</b><span style={{ color: '#666' }}>Access type: Internet</span></div>
              <div style={{ color: '#666', fontSize: 12 }}>Domain network · Connections: Ethernet0</div>
            </div>
            {os.adapters.map((a) => (
              <div key={a.id} className="winos-grid2" style={{ marginBottom: 10 }}>
                <span style={{ color: '#666' }}>{a.name}</span><span>{a.desc}</span>
                <span style={{ color: '#666' }}>IPv4 Address</span><span>{a.ipv4} / {a.mask}</span>
                <span style={{ color: '#666' }}>Default Gateway</span><span>{a.gateway}</span>
                <span style={{ color: '#666' }}>DNS Servers</span><span>{a.dns.join(', ')}</span>
              </div>
            ))}
            <button className="winos-btn" onClick={() => os.openApp('Terminal', { shell: 'cmd' }, { title: 'Command Prompt' })}>Open ncpa.cpl (command prompt)</button>
          </Section>
        )}

        {view === 'hw' && (
          <Section title="Devices and Printers">
            <div style={{ fontWeight: 600, fontSize: 12, margin: '6px 0' }}>Printers</div>
            {[['HP LaserJet Pro MFP', true], ['Microsoft Print to PDF', false], ['Microsoft XPS Document Writer', false], ['Send to OneNote', false]].map(([p, def]) => (
              <div key={p} style={{ padding: '3px 0' }}>🖨️ {p} {def && <span style={{ color: '#107c10' }}>✓ Default</span>}</div>
            ))}
            <div style={{ fontWeight: 600, fontSize: 12, margin: '10px 0 6px' }}>Power Options</div>
            <label style={{ display: 'block' }}><input type="radio" name="pwr" defaultChecked /> Balanced (recommended)</label>
            <label style={{ display: 'block' }}><input type="radio" name="pwr" /> High performance</label>
            <label style={{ display: 'block' }}><input type="radio" name="pwr" /> Power saver</label>
          </Section>
        )}

        {view === 'user' && (
          <Section title="User Accounts">
            <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 12 }}>
              <Users size={40} color="#16a085" />
              <div><div style={{ fontWeight: 600 }}>Administrator</div><div style={{ color: '#666', fontSize: 12 }}>Administrator · Password protected</div></div>
            </div>
            <a style={{ color: '#06c', display: 'block', cursor: 'default' }}>Change your account name</a>
            <a style={{ color: '#06c', display: 'block', cursor: 'default' }}>Change your account type</a>
            <a style={{ color: '#06c', display: 'block', cursor: 'default' }}>Manage another account</a>
            <a style={{ color: '#06c', display: 'block', cursor: 'default' }}>Change User Account Control settings</a>
          </Section>
        )}

        {view === 'clock' && (
          <Section title="Date and Time">
            <div className="winos-grid2">
              <span style={{ color: '#666' }}>Date</span><span>{new Date().toLocaleDateString()}</span>
              <span style={{ color: '#666' }}>Time</span><span>{new Date().toLocaleTimeString()}</span>
              <span style={{ color: '#666' }}>Time zone</span><select className="winos-input"><option>(UTC-05:00) Eastern Time (US & Canada)</option><option>(UTC-08:00) Pacific Time</option><option>(UTC+00:00) UTC</option></select>
              <span style={{ color: '#666' }}>Internet time</span><span>Synchronized with time.windows.com</span>
            </div>
          </Section>
        )}
      </div>

      {confirm && (
        <Dialog title="Programs and Features" onClose={() => setConfirm(null)}
          footer={<><button className="winos-btn primary" onClick={() => { os.uninstallProgram(confirm.name); setConfirm(null) }}>Yes</button><button className="winos-btn" onClick={() => setConfirm(null)}>No</button></>}>
          <p style={{ fontSize: 13 }}>Are you sure you want to uninstall <b>{confirm.name}</b>?</p>
        </Dialog>
      )}
    </div>
  )
}

const Section = ({ title, children }) => (
  <div className="winos-card" style={{ marginBottom: 16 }}>
    <div className="winos-card-h">{title}</div>
    <div style={{ padding: 14 }}>{children}</div>
  </div>
)
