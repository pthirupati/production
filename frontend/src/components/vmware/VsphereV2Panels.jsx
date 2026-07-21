import { useState } from 'react'

/** vSphere Client V2 admin blades — host profiles, SPBM, tags, DRS/HA, guest OS, LCM. */

function Panel({ title, children, action }) {
  return (
    <div className="vm-panel">
      <div className="vm-panel-header flex items-center justify-between gap-2">
        <span>{title}</span>
        {action}
      </div>
      <div className="vm-panel-body">{children}</div>
    </div>
  )
}

function HostProfiles({ rows = [], onAction, acting }) {
  return (
    <Panel
      title="Host Profiles"
      action={
        <button
          type="button"
          disabled={acting}
          className="vm-btn vm-btn-blue text-[10px] py-0.5 px-2"
          onClick={() => onAction('attach_host_profile', { name: `Profile-${(rows.length || 0) + 1}`, host: 'esxi-new.lab.local' })}
        >
          Attach profile…
        </button>
      }
    >
      <table className="vm-table">
        <thead>
          <tr>{['Name', 'Compliance', 'Hosts', ''].map((h) => <th key={h || 'x'}>{h}</th>)}</tr>
        </thead>
        <tbody>
          {(rows.length ? rows : []).map((p) => (
            <tr key={p.id}>
              <td className="text-[#5b9bf5]">{p.name}</td>
              <td>{p.compliance}</td>
              <td className="text-[#8FA5B8]">{(p.hosts || []).join(', ')}</td>
              <td>
                <button
                  type="button"
                  disabled={acting}
                  className="text-[10px] text-[#5b9bf5] hover:underline"
                  onClick={() => onAction('check_host_profile_compliance', { profile_id: p.id })}
                >
                  Check compliance
                </button>
              </td>
            </tr>
          ))}
          {!rows.length && (
            <tr><td colSpan={4} className="text-[#8FA5B8]">No host profiles</td></tr>
          )}
        </tbody>
      </table>
    </Panel>
  )
}

function StoragePolicies({ rows = [], onAction, acting }) {
  const [name, setName] = useState('')
  return (
    <Panel title="VM Storage Policies">
      <div className="mb-3 flex gap-2 flex-wrap">
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Policy name"
          className="vm-input !pl-3 text-xs flex-1 min-w-[140px]"
        />
        <button
          type="button"
          disabled={acting || !name.trim()}
          className="vm-btn vm-btn-blue text-xs"
          onClick={() => { onAction('create_storage_policy', { name: name.trim() }); setName('') }}
        >
          Create
        </button>
      </div>
      <table className="vm-table">
        <thead>
          <tr>{['Name', 'Rules', 'VMs'].map((h) => <th key={h}>{h}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((p) => (
            <tr key={p.id}>
              <td className="text-[#5b9bf5]">{p.name}</td>
              <td className="font-mono text-[11px]">{p.rules}</td>
              <td>{p.vms}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Panel>
  )
}

function TagsPanel({ rows = [], onAction, acting }) {
  const [category, setCategory] = useState('Environment')
  const [name, setName] = useState('')
  return (
    <Panel title="Tags & Categories">
      <div className="mb-3 flex gap-2 flex-wrap">
        <input value={category} onChange={(e) => setCategory(e.target.value)} placeholder="Category" className="vm-input !pl-3 text-xs w-36" />
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Tag name" className="vm-input !pl-3 text-xs flex-1 min-w-[120px]" />
        <button
          type="button"
          disabled={acting || !name.trim()}
          className="vm-btn vm-btn-blue text-xs"
          onClick={() => { onAction('create_tag', { category: category.trim(), name: name.trim() }); setName('') }}
        >
          Create tag
        </button>
      </div>
      <table className="vm-table">
        <thead>
          <tr>{['Category', 'Tag', 'Objects'].map((h) => <th key={h}>{h}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((t) => (
            <tr key={t.id}>
              <td>{t.category}</td>
              <td className="text-[#5b9bf5]">{t.name}</td>
              <td>{t.objects}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Panel>
  )
}

function DrsHaPanel({ rules = [], ha = {}, onAction, acting }) {
  const [ruleName, setRuleName] = useState('')
  return (
    <div className="space-y-3">
      <Panel title="vSphere HA">
        <div className="grid grid-cols-2 gap-2 text-[11px] mb-3">
          <div><span className="text-[#8FA5B8]">Enabled</span><div>{ha.enabled ? 'Yes' : 'No'}</div></div>
          <div><span className="text-[#8FA5B8]">Admission control</span><div>{ha.admission_control || '—'}</div></div>
          <div><span className="text-[#8FA5B8]">Host isolation</span><div>{ha.host_isolation || '—'}</div></div>
          <div><span className="text-[#8FA5B8]">VM monitoring</span><div>{ha.vm_monitoring || '—'}</div></div>
        </div>
        <button
          type="button"
          disabled={acting}
          className="vm-btn vm-btn-blue text-xs"
          onClick={() => onAction('update_ha_settings', { vm_monitoring: 'vmAndAppMonitoring', host_isolation: 'powerOff' })}
        >
          Apply recommended HA
        </button>
      </Panel>
      <Panel title="DRS Affinity Rules">
        <div className="mb-3 flex gap-2">
          <input value={ruleName} onChange={(e) => setRuleName(e.target.value)} placeholder="Rule name" className="vm-input !pl-3 text-xs flex-1" />
          <button
            type="button"
            disabled={acting || !ruleName.trim()}
            className="vm-btn vm-btn-blue text-xs"
            onClick={() => {
              onAction('create_drs_rule', { name: ruleName.trim(), type: 'SeparateVirtualMachines', vms: ['app-01', 'db-01'] })
              setRuleName('')
            }}
          >
            Add rule
          </button>
        </div>
        <table className="vm-table">
          <thead>
            <tr>{['Name', 'Type', 'Enabled', 'VMs'].map((h) => <th key={h}>{h}</th>)}</tr>
          </thead>
          <tbody>
            {rules.map((r) => (
              <tr key={r.id}>
                <td className="text-[#5b9bf5]">{r.name}</td>
                <td className="font-mono text-[11px]">{r.type}</td>
                <td>{r.enabled ? 'Yes' : 'No'}</td>
                <td className="text-[#8FA5B8]">{(r.vms || []).join(', ')}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Panel>
    </div>
  )
}

function GuestCustomizations({ rows = [], onAction, acting }) {
  const [name, setName] = useState('')
  return (
    <Panel title="Guest OS Customization Specifications">
      <div className="mb-3 flex gap-2">
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Spec name" className="vm-input !pl-3 text-xs flex-1" />
        <button
          type="button"
          disabled={acting || !name.trim()}
          className="vm-btn vm-btn-blue text-xs"
          onClick={() => { onAction('create_guest_customization', { name: name.trim(), os: 'Linux' }); setName('') }}
        >
          Create
        </button>
      </div>
      <table className="vm-table">
        <thead>
          <tr>{['Name', 'OS', 'Domain', 'Timezone'].map((h) => <th key={h}>{h}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((g) => (
            <tr key={g.id}>
              <td className="text-[#5b9bf5]">{g.name}</td>
              <td>{g.os}</td>
              <td>{g.domain}</td>
              <td>{g.timezone}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Panel>
  )
}

function LifecycleBaselines({ rows = [], onAction, acting }) {
  return (
    <Panel title="Lifecycle Manager — Baselines">
      <table className="vm-table">
        <thead>
          <tr>{['Name', 'Type', 'Compliant', 'Non-compliant', ''].map((h) => <th key={h || 'x'}>{h}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((b) => (
            <tr key={b.id}>
              <td className="text-[#5b9bf5]">{b.name}</td>
              <td>{b.type}</td>
              <td>{b.compliant_hosts}</td>
              <td>{b.non_compliant}</td>
              <td>
                {b.non_compliant > 0 && (
                  <button
                    type="button"
                    disabled={acting}
                    className="text-[10px] text-[#5b9bf5] hover:underline"
                    onClick={() => onAction('remediate_baseline', { baseline_id: b.id })}
                  >
                    Remediate
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Panel>
  )
}

/** Nav keys used by VmwareAdministration V2 section. */
export const VSPHERE_V2_NAV = [
  { key: 'hostprofiles', label: 'Host Profiles' },
  { key: 'storagepolicies', label: 'VM Storage Policies' },
  { key: 'tags', label: 'Tags & Categories' },
  { key: 'drsha', label: 'DRS & HA' },
  { key: 'guestcust', label: 'Guest Customization' },
  { key: 'lifecycle', label: 'Lifecycle Manager' },
]

export function renderVsphereV2Page({ view, inv = {}, onAction, acting }) {
  if (view === 'hostprofiles') return <HostProfiles rows={inv.host_profiles || []} onAction={onAction} acting={acting} />
  if (view === 'storagepolicies') return <StoragePolicies rows={inv.storage_policies || []} onAction={onAction} acting={acting} />
  if (view === 'tags') return <TagsPanel rows={inv.tags || []} onAction={onAction} acting={acting} />
  if (view === 'drsha') return <DrsHaPanel rules={inv.drs_rules || []} ha={inv.ha_settings || {}} onAction={onAction} acting={acting} />
  if (view === 'guestcust') return <GuestCustomizations rows={inv.guest_customizations || []} onAction={onAction} acting={acting} />
  if (view === 'lifecycle') return <LifecycleBaselines rows={inv.lifecycle_baselines || []} onAction={onAction} acting={acting} />
  return null
}
