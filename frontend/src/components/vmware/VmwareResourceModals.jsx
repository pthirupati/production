import { useState } from 'react'

/* Shared modal chrome matching the dark vSphere theme. All text uses the
   light --vm-text / explicit hex tokens so nothing renders white-on-white. */
function Modal({ title, onClose, children, footer, width = 'w-[440px]' }) {
  return (
    <div className="vm-modal-overlay">
      <div className={`vm-modal ${width} max-w-[95vw]`}>
        <div className="vm-modal-header">
          <span>{title}</span>
          <button type="button" onClick={onClose} className="text-[#8fa5b8] hover:text-white">✕</button>
        </div>
        <div className="vm-modal-body space-y-3">{children}</div>
        <div className="vm-modal-footer">{footer}</div>
      </div>
    </div>
  )
}

function Field({ label, children }) {
  return (
    <div>
      <label className="block text-xs text-[#8fa5b8] mb-1">{label}</label>
      {children}
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
export function CreateVswitchModal({ hosts = [], onClose, onAction }) {
  const [name, setName] = useState('')
  const [type, setType] = useState('standard')
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
