import { useState } from 'react'

/* Host Configure tab — real vSphere left sub-nav with detail panels rendered
   from host state. Sections: Hardware (Overview / Processors / Memory / PCI
   Devices / Power Management), Networking (Virtual switches / VMkernel adapters
   / Physical adapters / TCP-IP), Storage (Adapters / Devices / Datastores),
   System (Licensing / Host Profile / Time Configuration / Authentication /
   Certificate / Advanced Settings), and Health Status. */

const fmtSpeed = (mbps) => mbps >= 1000 ? `${mbps / 1000} Gbps` : `${mbps} Mbps`
const fmtGhz = (mhz) => `${(mhz / 1000).toFixed(2)} GHz`

const NAV = [
  {
    group: 'Hardware',
    items: [
      ['overview', 'Overview'],
      ['processors', 'Processors'],
      ['memory', 'Memory'],
      ['pci', 'PCI Devices'],
      ['power', 'Power Management'],
    ],
  },
  {
    group: 'Networking',
    items: [
      ['vswitches', 'Virtual switches'],
      ['vmkernel', 'VMkernel adapters'],
      ['physical', 'Physical adapters'],
      ['tcpip', 'TCP/IP configuration'],
    ],
  },
  {
    group: 'Storage',
    items: [
      ['adapters', 'Storage Adapters'],
      ['devices', 'Storage Devices'],
      ['hostdatastores', 'Datastores'],
    ],
  },
  {
    group: 'System',
    items: [
      ['licensing', 'Licensing'],
      ['hostprofile', 'Host Profile'],
      ['time', 'Time Configuration'],
      ['auth', 'Authentication Services'],
      ['certificate', 'Certificate'],
      ['advanced', 'Advanced System Settings'],
    ],
  },
  {
    group: 'Health',
    items: [['health', 'Health Status']],
  },
]

function Panel({ title, action, children }) {
  return (
    <div className="vm-panel">
      <div className="vm-panel-header flex items-center justify-between">
        <span>{title}</span>
        {action}
      </div>
      <div className="vm-panel-body">{children}</div>
    </div>
  )
}

function Row({ label, value, color }) {
  return (
    <div className="vm-info-row">
      <span className="vm-info-label">{label}</span>
      <span className="vm-info-value" style={color ? { color } : undefined}>{value ?? '—'}</span>
    </div>
  )
}

export default function VmwareHostConfigurePanel({ host, datastores = [], networks = [], vswitches = [], vms = [], licensing = {}, onAction, acting }) {
  const [sub, setSub] = useState('overview')
  if (!host) return null

  const cores = (host.cpu_sockets || 0) * (host.cpu_cores_per_socket || 0)
  const threads = host.cpu_threads || cores * 2
  const hostVswitches = vswitches.filter(v => v.type === 'standard' ? v.host === host.id : (v.hosts || []).includes(host.id))
  const hostNets = networks.filter(n => (n.hosts || []).includes(host.id))
  const hostDatastores = datastores.filter(d => (d.hosts || []).includes(host.id))

  const renderBody = () => {
    switch (sub) {
      case 'overview':
        return (
          <div className="space-y-3">
            <Panel title="Hardware Overview">
              <Row label="Manufacturer" value={host.vendor} />
              <Row label="Model" value={host.model} />
              <Row label="Processor Type" value={host.cpu_model} />
              <Row label="Logical Processors" value={threads} />
              <Row label="Sockets" value={host.cpu_sockets} />
              <Row label="Cores per Socket" value={host.cpu_cores_per_socket} />
              <Row label="Memory" value={`${host.memory_gb} GB`} />
              <Row label="Network Adapters" value={(host.vmnics || []).length || host.network_adapters} />
              <Row label="ESXi Version" value={`${host.version} (build ${host.build || '—'})`} />
              <Row label="Uptime status" value={host.maintenance ? 'Maintenance Mode' : 'Operational'} color={host.maintenance ? '#F5A623' : '#5DB85D'} />
            </Panel>
          </div>
        )
      case 'processors':
        return (
          <Panel title="Processors">
            <Row label="Model" value={host.cpu_model} />
            <Row label="Processor Sockets" value={host.cpu_sockets} />
            <Row label="Cores per Socket" value={host.cpu_cores_per_socket} />
            <Row label="Logical Processors (threads)" value={threads} />
            <Row label="Processor Speed" value={fmtGhz(host.cpu_mhz || 0)} />
            <Row label="Hyperthreading" value="Active" color="#5DB85D" />
            <Row label="Current usage" value={`${host.cpu_pct ?? 0}%`} />
          </Panel>
        )
      case 'memory':
        return (
          <Panel title="Memory">
            <Row label="Total Memory" value={`${host.memory_gb} GB`} />
            <Row label="System (VMkernel)" value={`${Math.max(2, Math.round(host.memory_gb * 0.06))} GB`} />
            <Row label="Virtual Machines" value={`${Math.round(host.memory_gb * (host.mem_pct ?? 0) / 100)} GB`} />
            <Row label="Free" value={`${Math.round(host.memory_gb * (100 - (host.mem_pct ?? 0)) / 100)} GB`} color="#5DB85D" />
            <Row label="Current usage" value={`${host.mem_pct ?? 0}%`} />
          </Panel>
        )
      case 'pci':
        return (
          <Panel title="PCI Devices">
            <table className="vm-table">
              <thead><tr>{['ID', 'Device', 'Vendor', 'Driver'].map(h => <th key={h}>{h}</th>)}</tr></thead>
              <tbody>
                {(host.vmnics || []).map(v => (
                  <tr key={v.id}>
                    <td className="font-mono text-[10px] text-[#8FA5B8]">{v.pci_id}</td>
                    <td>{v.name} Ethernet Controller</td>
                    <td className="text-[#8FA5B8]">Broadcom Inc.</td>
                    <td className="text-[#8FA5B8]">{v.driver}</td>
                  </tr>
                ))}
                <tr>
                  <td className="font-mono text-[10px] text-[#8FA5B8]">0000:00:1f.2</td>
                  <td>Lewisburg SATA AHCI Controller</td>
                  <td className="text-[#8FA5B8]">Intel Corporation</td>
                  <td className="text-[#8FA5B8]">vmw_ahci</td>
                </tr>
              </tbody>
            </table>
          </Panel>
        )
      case 'power':
        return (
          <Panel
            title="Power Management"
            action={
              <span className="text-[10px] text-[#8FA5B8] uppercase tracking-wide">{host.power_policy || 'Balanced'}</span>
            }
          >
            <Row label="Active Policy" value={host.power_policy || 'Balanced'} />
            <Row label="Technology" value="ACPI P-states, C-states" />
            <p className="text-[11px] text-[#8FA5B8] mt-2">
              Balances power consumption against performance based on workload.
            </p>
          </Panel>
        )
      case 'vswitches':
        return (
          <Panel
            title="Virtual switches"
            action={<button type="button" disabled={acting} onClick={() => onAction('__create_vswitch__', host)} className="vm-btn vm-btn-blue text-[10px] py-0.5 px-2">Add Networking…</button>}
          >
            {hostVswitches.length === 0 ? <p className="text-[#8FA5B8] text-[11px]">No virtual switches on this host.</p> : hostVswitches.map(vsw => (
              <div key={vsw.id} className="border border-[#2D3A4A] rounded p-2.5 mb-2 bg-[#16222f]">
                <p className="text-[11px] font-semibold text-[#E8EDF2] m-0">{vsw.name} <span className="text-[10px] text-[#8FA5B8] font-normal">({vsw.type})</span></p>
                <div className="grid grid-cols-3 gap-1 mt-1 text-[10px] text-[#8FA5B8]">
                  <span>Ports: {vsw.ports}</span>
                  <span>MTU: {vsw.mtu}</span>
                  <span>Uplinks: {vsw.uplinks?.join(', ') || '—'}</span>
                </div>
                <p className="text-[10px] text-[#8FA5B8] mt-0.5">Port groups: {vsw.portgroups?.join(', ') || '—'}</p>
              </div>
            ))}
          </Panel>
        )
      case 'vmkernel':
        return (
          <Panel title="VMkernel adapters">
            <table className="vm-table">
              <thead><tr>{['Device', 'Network Label', 'IP Address', 'TCP/IP Stack', 'Services'].map(h => <th key={h}>{h}</th>)}</tr></thead>
              <tbody>
                <tr><td className="text-[#5b9bf5]">vmk0</td><td>Management Network</td><td className="font-mono text-[10px]">{host.ip}</td><td>Default</td><td className="text-[#8FA5B8]">Management</td></tr>
                <tr><td className="text-[#5b9bf5]">vmk1</td><td>vMotion</td><td className="font-mono text-[10px]">192.168.20.{host.id.slice(-1) || 1}1</td><td>vMotion</td><td className="text-[#8FA5B8]">vMotion</td></tr>
                <tr><td className="text-[#5b9bf5]">vmk2</td><td>Storage-VLAN-200</td><td className="font-mono text-[10px]">10.200.0.{host.id.slice(-1) || 1}1</td><td>Default</td><td className="text-[#8FA5B8]">Provisioning</td></tr>
              </tbody>
            </table>
          </Panel>
        )
      case 'physical':
        return (
          <Panel
            title="Physical adapters"
            action={<button type="button" disabled={acting} onClick={() => onAction('add_host_uplink', { host_id: host.id })} className="vm-btn text-[10px] py-0.5 px-2">Add uplink (vmnic)</button>}
          >
            <table className="vm-table">
              <thead><tr>{['Device', 'MAC Address', 'Driver', 'Speed', 'Switch', 'Status'].map(h => <th key={h}>{h}</th>)}</tr></thead>
              <tbody>
                {(host.vmnics || []).map(v => (
                  <tr key={v.id}>
                    <td className="text-[#5b9bf5] font-semibold">{v.name}</td>
                    <td className="font-mono text-[10px] text-[#8FA5B8]">{v.mac_address}</td>
                    <td className="text-[#8FA5B8]">{v.driver}</td>
                    <td>{fmtSpeed(v.speed_mbps)}</td>
                    <td>{v.switch}</td>
                    <td className={v.status === 'up' ? 'text-[#5DB85D] font-semibold' : 'text-[#D9534F]'}>{v.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Panel>
        )
      case 'tcpip':
        return (
          <Panel title="TCP/IP configuration">
            <Row label="Host name" value={host.name?.split('.')[0]} />
            <Row label="Domain" value={host.name?.split('.').slice(1).join('.') || 'fixitlab.local'} />
            <Row label="Default gateway" value="192.168.10.1" />
            <Row label="DNS servers" value={(host.dns_servers || []).join(', ')} />
            <Row label="Default TCP/IP stack" value="defaultTcpipStack" />
          </Panel>
        )
      case 'adapters':
        return (
          <Panel
            title="Storage Adapters"
            action={<button type="button" disabled={acting} onClick={() => onAction('rescan_storage', { host_id: host.id })} className="vm-btn text-[10px] py-0.5 px-2">Rescan Storage</button>}
          >
            <table className="vm-table">
              <thead><tr>{['Adapter', 'Type', 'Status', 'Identifier'].map(h => <th key={h}>{h}</th>)}</tr></thead>
              <tbody>
                <tr><td className="text-[#5b9bf5]">vmhba0</td><td>Block SCSI</td><td className="text-[#5DB85D]">Online</td><td className="font-mono text-[10px] text-[#8FA5B8]">vmhba0</td></tr>
                <tr><td className="text-[#5b9bf5]">vmhba64</td><td>iSCSI Software Adapter</td><td className="text-[#5DB85D]">Online</td><td className="font-mono text-[10px] text-[#8FA5B8]">iqn.1998-01.com.vmware</td></tr>
                {host.hba_rescan_done && <tr><td colSpan={4} className="text-[10px] text-[#5DB85D]">✓ Rescan completed — devices up to date</td></tr>}
              </tbody>
            </table>
          </Panel>
        )
      case 'devices':
        return (
          <Panel title="Storage Devices">
            <table className="vm-table">
              <thead><tr>{['Name', 'Type', 'Capacity', 'Datastore'].map(h => <th key={h}>{h}</th>)}</tr></thead>
              <tbody>
                {hostDatastores.map(ds => (
                  <tr key={ds.id}>
                    <td className="font-mono text-[10px] text-[#8FA5B8]">{ds.extent_name || `naa.${ds.id}`}</td>
                    <td>disk</td>
                    <td>{ds.capacity_gb >= 1024 ? `${(ds.capacity_gb / 1024).toFixed(1)} TB` : `${ds.capacity_gb} GB`}</td>
                    <td className="text-[#5b9bf5]">{ds.name}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Panel>
        )
      case 'hostdatastores':
        return (
          <Panel
            title="Datastores"
            action={<button type="button" disabled={acting} onClick={() => onAction('__create_datastore__', host)} className="vm-btn vm-btn-blue text-[10px] py-0.5 px-2">New Datastore…</button>}
          >
            <table className="vm-table">
              <thead><tr>{['Name', 'Type', 'Capacity', 'Free', 'Accessible'].map(h => <th key={h}>{h}</th>)}</tr></thead>
              <tbody>
                {hostDatastores.map(ds => (
                  <tr key={ds.id}>
                    <td className="text-[#5b9bf5]">{ds.name}</td>
                    <td>{ds.type}</td>
                    <td>{ds.capacity_gb >= 1024 ? `${(ds.capacity_gb / 1024).toFixed(1)} TB` : `${ds.capacity_gb} GB`}</td>
                    <td className={ds.free_gb < 50 ? 'text-[#D9534F]' : 'text-[#5DB85D]'}>{ds.free_gb >= 1024 ? `${(ds.free_gb / 1024).toFixed(1)} TB` : `${ds.free_gb} GB`}</td>
                    <td className={ds.accessible ? 'text-[#5DB85D]' : 'text-[#D9534F]'}>{ds.accessible ? 'Yes' : 'No'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Panel>
        )
      case 'licensing':
        return (
          <Panel title="Licensing">
            <Row label="Product" value={licensing.product || 'VMware vSphere 7 Hypervisor'} color="#5b9bf5" />
            <Row label="License Key" value={<span className="font-mono">{licensing.license_key_masked || 'XXXXX-XXXXX-XXXXX-XXXXX-XXXXX'}</span>} />
            <Row label="Capacity" value={licensing.capacity || 'Unlimited CPUs'} />
            <Row label="Used" value={licensing.used || '—'} />
            <Row label="Expires" value={licensing.expiry || 'Never'} color="#5DB85D" />
            <div className="mt-3">
              <p className="text-[11px] font-semibold text-[#E8EDF2] mb-1.5">Features</p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-1">
                {(licensing.features || []).map(f => (
                  <div key={f} className="flex items-center gap-1.5 text-[11px] text-[#c3d3e3]">
                    <span className="text-[#5DB85D]">✓</span>{f}
                  </div>
                ))}
              </div>
            </div>
          </Panel>
        )
      case 'hostprofile':
        return (
          <Panel
            title="Host Profile"
            action={
              <span className="flex gap-1.5">
                <button type="button" disabled={acting} onClick={() => onAction('extract_host_profile', { host_id: host.id })} className="vm-btn vm-btn-blue text-[10px] py-0.5 px-2">Extract Profile…</button>
              </span>
            }
          >
            {host.host_profile ? (
              <>
                <Row label="Attached Profile" value={host.host_profile} color="#5b9bf5" />
                <Row label="Compliance" value="Compliant" color="#5DB85D" />
              </>
            ) : (
              <p className="text-[11px] text-[#8FA5B8]">No host profile attached. Extract a profile from this host to standardise configuration across the cluster.</p>
            )}
          </Panel>
        )
      case 'time':
        return (
          <Panel
            title="Time Configuration"
            action={<button type="button" disabled={acting} onClick={() => onAction('sync_ntp', { host_id: host.id })} className="vm-btn text-[10px] py-0.5 px-2">Synchronize NTP</button>}
          >
            <Row label="NTP Server" value={host.ntp_server || 'pool.ntp.org'} />
            <Row label="NTP Service" value={host.ntp_synced === false ? 'Out of sync' : 'Running (synced)'} color={host.ntp_synced === false ? '#D9534F' : '#5DB85D'} />
            <Row label="Time Zone" value="UTC" />
          </Panel>
        )
      case 'auth':
        return (
          <Panel title="Authentication Services">
            <Row label="Directory Services" value="Local Authentication" />
            <Row label="Domain" value="Not joined" />
            <Row label="Smart Card Authentication" value="Disabled" />
            <Row label="Lockdown Mode" value="Disabled" />
          </Panel>
        )
      case 'certificate':
        return (
          <Panel
            title="Certificate"
            action={<button type="button" disabled={acting} onClick={() => onAction('renew_host_cert', { host_id: host.id })} className="vm-btn vm-btn-blue text-[10px] py-0.5 px-2">Renew Certificate</button>}
          >
            <Row label="Issued To" value={host.name} />
            <Row label="Issued By" value="CA (vCenter VMCA)" />
            <Row label="Status" value={host.cert_expired ? 'Expired' : 'Valid'} color={host.cert_expired ? '#D9534F' : '#5DB85D'} />
            <Row label="Valid Until" value="2027-03-30" />
            {host.cert_renewed_at && <Row label="Last renewed" value={host.cert_renewed_at} />}
          </Panel>
        )
      case 'advanced':
        return (
          <Panel title="Advanced System Settings">
            <table className="vm-table">
              <thead><tr>{['Key', 'Value'].map(h => <th key={h}>{h}</th>)}</tr></thead>
              <tbody>
                {[
                  ['UserVars.SuppressShellWarning', host.ssh_enabled ? '1' : '0'],
                  ['Net.TcpipHeapSize', '32'],
                  ['Net.TcpipHeapMax', '1536'],
                  ['Mem.ShareForceSalting', '2'],
                  ['Misc.HostName', host.name],
                  ['Syslog.global.logHost', 'udp://syslog.fixitlab.local:514'],
                ].map(([k, v]) => (
                  <tr key={k}><td className="font-mono text-[10px] text-[#8FA5B8]">{k}</td><td className="font-mono text-[10px]">{v}</td></tr>
                ))}
              </tbody>
            </table>
          </Panel>
        )
      case 'health':
        return (
          <Panel title="Health Status">
            {[
              ['Processors', 'Normal'],
              ['Memory', 'Normal'],
              ['Storage', host.storage_pct > 90 ? 'Warning' : 'Normal'],
              ['Network', 'Normal'],
              ['Power', 'Normal'],
              ['Temperature', 'Normal'],
              ['Fans', 'Normal'],
            ].map(([sensor, status]) => (
              <div key={sensor} className="flex items-center gap-2 py-1.5 border-b border-[#22303f] last:border-0">
                <span className={`w-2 h-2 rounded-full ${status === 'Normal' ? 'bg-[#5DB85D]' : 'bg-[#F5A623]'}`} />
                <span className="text-[11px] text-[#E8EDF2] flex-1">{sensor}</span>
                <span className={`text-[11px] ${status === 'Normal' ? 'text-[#5DB85D]' : 'text-[#F5A623]'}`}>{status}</span>
              </div>
            ))}
          </Panel>
        )
      default:
        return null
    }
  }

  return (
    <div className="flex gap-3 min-h-0">
      {/* Left sub-nav */}
      <div className="w-48 shrink-0 border border-[#2D3A4A] rounded-lg bg-[#16222f] overflow-y-auto py-1.5">
        {NAV.map(({ group, items }) => (
          <div key={group} className="mb-1">
            <p className="px-3 py-1 text-[10px] font-bold text-[#6880a0] uppercase tracking-wider m-0">{group}</p>
            {items.map(([id, label]) => (
              <button
                key={id}
                type="button"
                onClick={() => setSub(id)}
                className={`w-full text-left px-3 py-1.5 text-[11.5px] ${sub === id ? 'bg-[rgba(45,124,255,.15)] text-white border-l-2 border-[#2D7CFF]' : 'text-[#c3d3e3] hover:bg-white/[0.05] border-l-2 border-transparent'}`}
              >
                {label}
              </button>
            ))}
          </div>
        ))}
      </div>
      {/* Detail panel */}
      <div className="flex-1 min-w-0">{renderBody()}</div>
    </div>
  )
}
