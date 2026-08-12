import { cloneElement, isValidElement, useId, useState } from 'react'
import VmModal from './VmModal'

/* Shared modal chrome matching the dark vSphere theme. All text uses the
   light --vm-text / explicit hex tokens so nothing renders white-on-white. */
function Modal({ title, onClose, children, footer, width = 'w-[440px]' }) {
  // Prefer the shared VmModal shell (a11y trap + overlay) so orphanModules
  // stays green and every vSphere modal shares one chrome implementation.
  return (
    <VmModal title={title} onClose={onClose} footer={footer} width={`${width} max-w-[95vw]`}>
      <div className="space-y-3">{children}</div>
    </VmModal>
  )
}

/* The visible <label> already carries the vSphere wording learners are being
   taught, so we bind it to the control with htmlFor/id rather than duplicating
   it in an aria-label — a second, hand-written name is what drifts out of sync
   with the emulated product. A caller-supplied id wins so nothing is clobbered. */
function Field({ label, children }) {
  const generatedId = useId()
  const controlId = isValidElement(children) ? (children.props.id || generatedId) : undefined
  return (
    <div>
      <label htmlFor={controlId} className="block text-xs text-[#8fa5b8] mb-1">{label}</label>
      {isValidElement(children) ? cloneElement(children, { id: controlId }) : children}
    </div>
  )
}

function useSubmit(onAction, onClose) {
  const [acting, setActing] = useState(false)
  const [error, setError] = useState('')
  const run = async (action, payload) => {
    setActing(true); setError('')
    try {
      await onAction(action, payload)
      onClose()
    } catch (e) {
      setError(e?.response?.data?.error || 'Action failed')
    } finally {
      setActing(false)
    }
  }
  return { acting, error, run }
}

/* ─── Add Disk ───────────────────────────────────────────────────────── */
export function AddDiskModal({ vm, datastores = [], onClose, onAction }) {
  const [sizeGb, setSizeGb] = useState('100')
  const [provisioning, setProvisioning] = useState('thin')
  const [dsId, setDsId] = useState(vm.datastore_id || datastores[0]?.id || '')
  const { acting, error, run } = useSubmit(onAction, onClose)
  const used = (vm.disks || []).map(d => d.scsi_unit ?? 0)
  let nextUnit = 0
  while (used.includes(nextUnit) || nextUnit === 7) nextUnit += 1

  return (
    <Modal title={`Add Hard Disk — ${vm.name}`} onClose={onClose}
      footer={<>
        <button type="button" onClick={onClose} className="vm-btn">Cancel</button>
        <button type="button" disabled={acting} className="vm-btn vm-btn-blue"
          onClick={() => run('add_disk', { vm_id: vm.id, size_gb: parseInt(sizeGb) || 100, thin: provisioning === 'thin', datastore_id: dsId })}>
          {acting ? 'Adding…' : 'Add disk'}
        </button>
      </>}>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Size (GB)">
          <input type="number" min="10" value={sizeGb} onChange={e => setSizeGb(e.target.value)} className="vm-input !pl-3" />
        </Field>
        <Field label="Provisioning">
          <select value={provisioning} onChange={e => setProvisioning(e.target.value)} className="vm-input !pl-3">
            <option value="thin">Thin provision</option>
            <option value="thick">Thick provision (eager)</option>
          </select>
        </Field>
        <Field label="Datastore">
          <select value={dsId} onChange={e => setDsId(e.target.value)} className="vm-input !pl-3">
            {datastores.filter(d => d.accessible).map(d => (
              <option key={d.id} value={d.id}>{d.name}</option>
            ))}
          </select>
        </Field>
        <Field label="SCSI node (auto)">
          <input value={`SCSI 0:${nextUnit}`} disabled className="vm-input !pl-3 opacity-70" />
        </Field>
      </div>
      <p className="text-[10px] text-[#8fa5b8]">A new virtual disk is attached on the next free SCSI node. Boot disk stays at 0:0.</p>
      {error && <p className="text-xs text-[#D9534F]">{error}</p>}
    </Modal>
  )
}

/* ─── Add Network Adapter ────────────────────────────────────────────── */
export function AddNicModal({ vm, networks = [], onClose, onAction }) {
  const [netId, setNetId] = useState(vm.network_id || networks[0]?.id || '')
  const [adapter, setAdapter] = useState('Vmxnet3')
  const { acting, error, run } = useSubmit(onAction, onClose)

  return (
    <Modal title={`Add Network Adapter — ${vm.name}`} onClose={onClose}
      footer={<>
        <button type="button" onClick={onClose} className="vm-btn">Cancel</button>
        <button type="button" disabled={acting || !netId} className="vm-btn vm-btn-blue"
          onClick={() => run('add_nic', { vm_id: vm.id, network_id: netId, adapter_type: adapter })}>
          {acting ? 'Adding…' : 'Add adapter'}
        </button>
      </>}>
      <Field label="Port group / network">
        <select value={netId} onChange={e => setNetId(e.target.value)} className="vm-input !pl-3">
          {networks.map(n => <option key={n.id} value={n.id}>{n.name}{(n.vlan_id ?? n.vlan) ? ` (VLAN ${n.vlan_id ?? n.vlan})` : ''}</option>)}
        </select>
      </Field>
      <Field label="Adapter type">
        <select value={adapter} onChange={e => setAdapter(e.target.value)} className="vm-input !pl-3">
          {['Vmxnet3', 'E1000E', 'E1000', 'PVRDMA'].map(a => <option key={a} value={a}>{a}</option>)}
        </select>
      </Field>
      <p className="text-[10px] text-[#8fa5b8]">A VMware MAC (00:50:56:xx:xx:xx) is auto-assigned to the new adapter.</p>
      {error && <p className="text-xs text-[#D9534F]">{error}</p>}
    </Modal>
  )
}

/* ─── Create Standard / Distributed vSwitch ──────────────────────────── */
export function CreateVswitchModal({ hosts = [], defaultType = 'standard', onClose, onAction }) {
  const [name, setName] = useState('')
  const [type, setType] = useState(defaultType)
  const [mtu, setMtu] = useState('1500')
  const [hostId, setHostId] = useState(hosts[0]?.id || '')
  const { acting, error, run } = useSubmit(onAction, onClose)

  return (
    <Modal title="New Virtual Switch" onClose={onClose}
      footer={<>
        <button type="button" onClick={onClose} className="vm-btn">Cancel</button>
        <button type="button" disabled={acting || !name.trim()} className="vm-btn vm-btn-blue"
          onClick={() => run('create_vswitch', { name: name.trim(), type, mtu: parseInt(mtu) || 1500, host_id: hostId })}>
          {acting ? 'Creating…' : 'Create switch'}
        </button>
      </>}>
      <Field label="Switch name *">
        <input value={name} onChange={e => setName(e.target.value)} placeholder="vSwitch1 / dvSwitch-DMZ" className="vm-input !pl-3" />
      </Field>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Type">
          <select value={type} onChange={e => setType(e.target.value)} className="vm-input !pl-3">
            <option value="standard">Standard switch</option>
            <option value="distributed">Distributed switch (DVS)</option>
          </select>
        </Field>
        <Field label="MTU">
          <select value={mtu} onChange={e => setMtu(e.target.value)} className="vm-input !pl-3">
            {['1500', '9000'].map(m => <option key={m} value={m}>{m}{m === '9000' ? ' (jumbo)' : ''}</option>)}
          </select>
        </Field>
        {type === 'standard' && (
          <Field label="Host">
            <select value={hostId} onChange={e => setHostId(e.target.value)} className="vm-input !pl-3">
              {hosts.map(h => <option key={h.id} value={h.id}>{h.name}</option>)}
            </select>
          </Field>
        )}
      </div>
      {error && <p className="text-xs text-[#D9534F]">{error}</p>}
    </Modal>
  )
}

/* ─── Create Port Group / VLAN ───────────────────────────────────────── */
export function CreatePortGroupModal({ vswitches = [], onClose, onAction }) {
  const [name, setName] = useState('')
  const [vlan, setVlan] = useState('0')
  const [switchName, setSwitchName] = useState(vswitches[0]?.name || 'vSwitch0')
  const { acting, error, run } = useSubmit(onAction, onClose)

  return (
    <Modal title="New Port Group / VLAN" onClose={onClose}
      footer={<>
        <button type="button" onClick={onClose} className="vm-btn">Cancel</button>
        <button type="button" disabled={acting || !name.trim()} className="vm-btn vm-btn-blue"
          onClick={() => run('create_portgroup', { name: name.trim(), vlan: parseInt(vlan) || 0, switch: switchName })}>
          {acting ? 'Creating…' : 'Create port group'}
        </button>
      </>}>
      <Field label="Port group name *">
        <input value={name} onChange={e => setName(e.target.value)} placeholder="Prod-VLAN-120" className="vm-input !pl-3" />
      </Field>
      <div className="grid grid-cols-2 gap-3">
        <Field label="VLAN ID (0 = none)">
          <input type="number" min="0" max="4094" value={vlan} onChange={e => setVlan(e.target.value)} className="vm-input !pl-3" />
        </Field>
        <Field label="Virtual switch">
          <select value={switchName} onChange={e => setSwitchName(e.target.value)} className="vm-input !pl-3">
            {(vswitches.length ? vswitches : [{ name: 'vSwitch0' }]).map(v => (
              <option key={v.id || v.name} value={v.name}>{v.name}</option>
            ))}
          </select>
        </Field>
      </div>
      {error && <p className="text-xs text-[#D9534F]">{error}</p>}
    </Modal>
  )
}

/* ─── Create Datastore ───────────────────────────────────────────────── */
export function CreateDatastoreModal({ onClose, onAction }) {
  const [name, setName] = useState('')
  const [type, setType] = useState('VMFS')
  const [capacityGb, setCapacityGb] = useState('512')
  const { acting, error, run } = useSubmit(onAction, onClose)

  return (
    <Modal title="New Datastore" onClose={onClose}
      footer={<>
        <button type="button" onClick={onClose} className="vm-btn">Cancel</button>
        <button type="button" disabled={acting || !name.trim()} className="vm-btn vm-btn-blue"
          onClick={() => run('create_datastore', { name: name.trim(), type, capacity_gb: parseInt(capacityGb) || 512 })}>
          {acting ? 'Creating…' : 'Create datastore'}
        </button>
      </>}>
      <Field label="Datastore name *">
        <input value={name} onChange={e => setName(e.target.value)} placeholder="datastore-nvme-02" className="vm-input !pl-3" />
      </Field>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Type">
          <select value={type} onChange={e => setType(e.target.value)} className="vm-input !pl-3">
            {['VMFS', 'NFS', 'vSAN'].map(t => <option key={t} value={t}>{t}</option>)}
          </select>
        </Field>
        <Field label="Capacity (GB)">
          <input type="number" min="10" value={capacityGb} onChange={e => setCapacityGb(e.target.value)} className="vm-input !pl-3" />
        </Field>
      </div>
      {error && <p className="text-xs text-[#D9534F]">{error}</p>}
    </Modal>
  )
}

/* ─── Create Cluster ─────────────────────────────────────────────────── */
export function CreateClusterModal({ datacenters = [], onClose, onAction }) {
  const [name, setName] = useState('')
  const [dcId, setDcId] = useState(datacenters[0]?.id || '')
  const [ha, setHa] = useState(true)
  const [drs, setDrs] = useState(true)
  const [vsan, setVsan] = useState(false)
  const { acting, error, run } = useSubmit(onAction, onClose)

  const toggle = (val, set, label) => (
    <label className="flex items-center gap-2 text-xs text-[#E8EDF2] cursor-pointer">
      <input type="checkbox" checked={val} onChange={e => set(e.target.checked)} />
      {label}
    </label>
  )

  return (
    <Modal title="New Cluster" onClose={onClose}
      footer={<>
        <button type="button" onClick={onClose} className="vm-btn">Cancel</button>
        <button type="button" disabled={acting || !name.trim()} className="vm-btn vm-btn-blue"
          onClick={() => run('create_cluster', { name: name.trim(), datacenter_id: dcId, ha, drs, vsan })}>
          {acting ? 'Creating…' : 'Create cluster'}
        </button>
      </>}>
      <Field label="Cluster name *">
        <input value={name} onChange={e => setName(e.target.value)} placeholder="Cluster-02" className="vm-input !pl-3" />
      </Field>
      {datacenters.length > 0 && (
        <Field label="Datacenter">
          <select value={dcId} onChange={e => setDcId(e.target.value)} className="vm-input !pl-3">
            {datacenters.map(d => <option key={d.id} value={d.id}>{d.name}</option>)}
          </select>
        </Field>
      )}
      <div className="space-y-2 pt-1">
        {toggle(ha, setHa, 'Turn ON vSphere HA')}
        {toggle(drs, setDrs, 'Turn ON vSphere DRS')}
        {toggle(vsan, setVsan, 'Enable vSAN')}
      </div>
      {error && <p className="text-xs text-[#D9534F]">{error}</p>}
    </Modal>
  )
}

/* ─── Add Host ───────────────────────────────────────────────────────── */
export function AddHostModal({ datacenters = [], onClose, onAction }) {
  const [name, setName] = useState('')
  const [ip, setIp] = useState('')
  const [memGb, setMemGb] = useState('128')
  const [dcId, setDcId] = useState(datacenters[0]?.id || 'dc-prod')
  const { acting, error, run } = useSubmit(onAction, onClose)

  return (
    <Modal title="Add Host" onClose={onClose}
      footer={<>
        <button type="button" onClick={onClose} className="vm-btn">Cancel</button>
        <button type="button" disabled={acting || !name.trim()} className="vm-btn vm-btn-blue"
          onClick={() => run('add_host', { name: name.trim(), ip: ip.trim() || undefined, memory_gb: parseInt(memGb) || 128, datacenter_id: dcId })}>
          {acting ? 'Adding…' : 'Add host'}
        </button>
      </>}>
      <Field label="Host name or IP *">
        <input value={name} onChange={e => setName(e.target.value)} placeholder="esxi-03.fixitlab.local" className="vm-input !pl-3" />
      </Field>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Management IP (optional)">
          <input value={ip} onChange={e => setIp(e.target.value)} placeholder="192.168.10.13" className="vm-input !pl-3" />
        </Field>
        <Field label="Memory (GB)">
          <select value={memGb} onChange={e => setMemGb(e.target.value)} className="vm-input !pl-3">
            {['64', '128', '256', '512', '1024'].map(m => <option key={m} value={m}>{m} GB</option>)}
          </select>
        </Field>
      </div>
      {datacenters.length > 0 && (
        <Field label="Datacenter">
          <select value={dcId} onChange={e => setDcId(e.target.value)} className="vm-input !pl-3">
            {datacenters.map(d => <option key={d.id} value={d.id}>{d.name}</option>)}
          </select>
        </Field>
      )}
      <p className="text-[10px] text-[#8fa5b8]">The host is added in connected state and attached to the datacenter's first cluster.</p>
      {error && <p className="text-xs text-[#D9534F]">{error}</p>}
    </Modal>
  )
}

/* ─── New Resource Pool ──────────────────────────────────────────────── */
export function CreateResourcePoolModal({ parentName = 'Cluster-01', onClose, onAction }) {
  const [name, setName] = useState('')
  const [cpuShares, setCpuShares] = useState('normal')
  const [memShares, setMemShares] = useState('normal')
  const [cpuLimit, setCpuLimit] = useState('-1')
  const [memLimit, setMemLimit] = useState('-1')
  const { acting, error, run } = useSubmit(onAction, onClose)

  return (
    <Modal title={`New Resource Pool — ${parentName}`} onClose={onClose}
      footer={<>
        <button type="button" onClick={onClose} className="vm-btn">Cancel</button>
        <button type="button" disabled={acting || !name.trim()} className="vm-btn vm-btn-blue"
          onClick={() => run('new_resource_pool', {
            name: name.trim(), parent: parentName, cpu_shares: cpuShares, mem_shares: memShares,
            cpu_limit_mhz: parseInt(cpuLimit), mem_limit_mb: parseInt(memLimit),
          })}>
          {acting ? 'Creating…' : 'Create pool'}
        </button>
      </>}>
      <Field label="Resource pool name *">
        <input value={name} onChange={e => setName(e.target.value)} placeholder="Production-RP" className="vm-input !pl-3" />
      </Field>
      <div className="grid grid-cols-2 gap-3">
        <Field label="CPU shares">
          <select value={cpuShares} onChange={e => setCpuShares(e.target.value)} className="vm-input !pl-3">
            {['low', 'normal', 'high'].map(s => <option key={s} value={s}>{s}</option>)}
          </select>
        </Field>
        <Field label="Memory shares">
          <select value={memShares} onChange={e => setMemShares(e.target.value)} className="vm-input !pl-3">
            {['low', 'normal', 'high'].map(s => <option key={s} value={s}>{s}</option>)}
          </select>
        </Field>
        <Field label="CPU limit (MHz, -1 = unlimited)">
          <input type="number" value={cpuLimit} onChange={e => setCpuLimit(e.target.value)} className="vm-input !pl-3" />
        </Field>
        <Field label="Memory limit (MB, -1 = unlimited)">
          <input type="number" value={memLimit} onChange={e => setMemLimit(e.target.value)} className="vm-input !pl-3" />
        </Field>
      </div>
      {error && <p className="text-xs text-[#D9534F]">{error}</p>}
    </Modal>
  )
}

/* ─── New vApp ───────────────────────────────────────────────────────── */
export function CreateVappModal({ parentName = 'Cluster-01', vms = [], onClose, onAction }) {
  const [name, setName] = useState('')
  const [selected, setSelected] = useState([])
  const { acting, error, run } = useSubmit(onAction, onClose)
  const toggleVm = (id) => setSelected(prev => prev.includes(id) ? prev.filter(v => v !== id) : [...prev, id])

  return (
    <Modal title={`New vApp — ${parentName}`} onClose={onClose}
      footer={<>
        <button type="button" onClick={onClose} className="vm-btn">Cancel</button>
        <button type="button" disabled={acting || !name.trim()} className="vm-btn vm-btn-blue"
          onClick={() => run('new_vapp', { name: name.trim(), parent: parentName, vms: selected })}>
          {acting ? 'Creating…' : 'Create vApp'}
        </button>
      </>}>
      <Field label="vApp name *">
        <input value={name} onChange={e => setName(e.target.value)} placeholder="3-Tier-App" className="vm-input !pl-3" />
      </Field>
      <Field label="Add virtual machines (optional)">
        <div className="max-h-40 overflow-y-auto border border-[#2d3a4a] rounded bg-[#16222f] p-2 space-y-1">
          {vms.length === 0 ? <p className="text-[10px] text-[#8fa5b8]">No VMs available</p> : vms.map(v => (
            <label key={v.id} className="flex items-center gap-2 text-xs text-[#E8EDF2] cursor-pointer">
              <input type="checkbox" checked={selected.includes(v.id)} onChange={() => toggleVm(v.id)} />
              {v.name}
            </label>
          ))}
        </div>
      </Field>
      <p className="text-[10px] text-[#8fa5b8]">Powering the vApp on/off cascades to its member VMs in start order.</p>
      {error && <p className="text-xs text-[#D9534F]">{error}</p>}
    </Modal>
  )
}

/* ─── New Datastore Cluster (SDRS) ───────────────────────────────────── */
export function CreateDatastoreClusterModal({ datastores = [], onClose, onAction }) {
  const [name, setName] = useState('')
  const [sdrs, setSdrs] = useState(true)
  const [automation, setAutomation] = useState('fullyAutomated')
  const [selected, setSelected] = useState([])
  const { acting, error, run } = useSubmit(onAction, onClose)
  const toggleDs = (id) => setSelected(prev => prev.includes(id) ? prev.filter(d => d !== id) : [...prev, id])

  return (
    <Modal title="New Datastore Cluster" onClose={onClose}
      footer={<>
        <button type="button" onClick={onClose} className="vm-btn">Cancel</button>
        <button type="button" disabled={acting || !name.trim()} className="vm-btn vm-btn-blue"
          onClick={() => run('create_datastore_cluster', { name: name.trim(), sdrs_enabled: sdrs, automation_level: automation, datastore_ids: selected })}>
          {acting ? 'Creating…' : 'Create cluster'}
        </button>
      </>}>
      <Field label="Datastore cluster name *">
        <input value={name} onChange={e => setName(e.target.value)} placeholder="SDRS-Prod" className="vm-input !pl-3" />
      </Field>
      <label className="flex items-center gap-2 text-xs text-[#E8EDF2] cursor-pointer">
        <input type="checkbox" checked={sdrs} onChange={e => setSdrs(e.target.checked)} />
        Turn ON Storage DRS
      </label>
      {sdrs && (
        <Field label="Automation level">
          <select value={automation} onChange={e => setAutomation(e.target.value)} className="vm-input !pl-3">
            <option value="manual">No Automation (Manual Mode)</option>
            <option value="fullyAutomated">Fully Automated</option>
          </select>
        </Field>
      )}
      <Field label="Member datastores">
        <div className="max-h-40 overflow-y-auto border border-[#2d3a4a] rounded bg-[#16222f] p-2 space-y-1">
          {datastores.length === 0 ? <p className="text-[10px] text-[#8fa5b8]">No datastores available</p> : datastores.map(d => (
            <label key={d.id} className="flex items-center gap-2 text-xs text-[#E8EDF2] cursor-pointer">
              <input type="checkbox" checked={selected.includes(d.id)} onChange={() => toggleDs(d.id)} />
              {d.name} <span className="text-[10px] text-[#8fa5b8]">({d.type})</span>
            </label>
          ))}
        </div>
      </Field>
      {error && <p className="text-xs text-[#D9534F]">{error}</p>}
    </Modal>
  )
}

/* ─── New Folder ─────────────────────────────────────────────────────── */
export function CreateFolderModal({ folderType = 'vm', datacenters = [], onClose, onAction }) {
  const [name, setName] = useState('')
  const [type, setType] = useState(folderType)
  const [dcId, setDcId] = useState(datacenters[0]?.id || 'dc-prod')
  const { acting, error, run } = useSubmit(onAction, onClose)

  return (
    <Modal title="New Folder" onClose={onClose}
      footer={<>
        <button type="button" onClick={onClose} className="vm-btn">Cancel</button>
        <button type="button" disabled={acting || !name.trim()} className="vm-btn vm-btn-blue"
          onClick={() => run('add_folder', { name: name.trim(), folder_type: type, datacenter_id: dcId })}>
          {acting ? 'Creating…' : 'Create folder'}
        </button>
      </>}>
      <Field label="Folder name *">
        <input value={name} onChange={e => setName(e.target.value)} placeholder="Production" className="vm-input !pl-3" />
      </Field>
      <Field label="Folder type">
        <select value={type} onChange={e => setType(e.target.value)} className="vm-input !pl-3">
          <option value="host">Host Folder</option>
          <option value="vm">VM Folder</option>
          <option value="storage">Storage Folder</option>
          <option value="network">Network Folder</option>
        </select>
      </Field>
      {datacenters.length > 0 && (
        <Field label="Datacenter">
          <select value={dcId} onChange={e => setDcId(e.target.value)} className="vm-input !pl-3">
            {datacenters.map(d => <option key={d.id} value={d.id}>{d.name}</option>)}
          </select>
        </Field>
      )}
      {error && <p className="text-xs text-[#D9534F]">{error}</p>}
    </Modal>
  )
}
