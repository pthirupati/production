import {
  Power, Camera, Copy, Settings, Trash2, Terminal, Pause, ArrowRightLeft, Pencil,
  HardDrive, Network, Wrench, RefreshCw, Plus, FolderOpen, Database, Server,
} from 'lucide-react'

/* Full vSphere-style right-click menu. Supports VMs, hosts, datastores and
   networks via the `kind` prop. `onAction` receives either a real engine
   action (e.g. 'power_on') or a UI sentinel (e.g. '__add_disk__') that the
   simulator maps to a modal. */
export default function VmwareContextMenu({ x, y, kind = 'vm', vm, node, onClose, onAction, onConsole, acting }) {
  const target = vm || node
  if (!target) return null

  let title = target.name
  let items = []

  if (kind === 'vm') {
    const isOn = vm.power === 'poweredOn'
    const isOff = vm.power === 'poweredOff'
    const toolsCurrent = (vm.vmware_tools_status || (vm.tools === 'ok' ? 'current' : 'notRunning')) === 'current'
    items = [
      { label: 'Power On', icon: Power, onClick: () => onAction('power_on', { vm_id: vm.id }), show: isOff, disabled: acting },
      { label: 'Power Off', icon: Power, onClick: () => onAction('power_off', { vm_id: vm.id }), show: isOn, disabled: acting, color: '#D9534F' },
      { label: 'Shut Down Guest OS', icon: Power, onClick: () => onAction('power_off_guest', { vm_id: vm.id }), show: isOn, disabled: acting },
      { label: 'Restart Guest OS', icon: Power, onClick: () => onAction('reboot_guest', { vm_id: vm.id }), show: isOn, disabled: acting },
      { label: 'Suspend', icon: Pause, onClick: () => onAction('__suspend__', vm), show: isOn, disabled: acting },
      { label: 'Reset', icon: Power, onClick: () => onAction('reboot', { vm_id: vm.id }), show: isOn, disabled: acting },
      { divider: true },
      { label: 'Take Snapshot…', icon: Camera, onClick: () => onAction('__snapshot__', vm), show: true },
      { label: 'Migrate…', icon: ArrowRightLeft, onClick: () => onAction('__migrate__', vm), show: true },
      { label: 'Clone…', icon: Copy, onClick: () => onAction('__clone__', vm), show: true },
      { divider: true },
      { label: 'Add Disk…', icon: HardDrive, onClick: () => onAction('__add_disk__', vm), show: true },
      { label: 'Add Network Adapter…', icon: Network, onClick: () => onAction('__add_nic__', vm), show: true },
      { label: 'Edit Settings…', icon: Settings, onClick: () => onAction('__edit__', vm), show: true },
      { label: 'Upgrade VMware Tools', icon: Wrench, onClick: () => onAction('upgrade_vmware_tools', { vm_id: vm.id }), show: !toolsCurrent, disabled: acting },
      { label: 'Rename…', icon: Pencil, onClick: () => onAction('__rename__', vm), show: true },
      { divider: true },
      { label: 'Open Console', icon: Terminal, onClick: () => { onConsole(vm); onClose() }, show: true },
      { divider: true },
      { label: 'Delete from Disk', icon: Trash2, onClick: () => onAction('__delete__', vm), show: !isOn, disabled: acting, color: '#D9534F' },
    ]
  } else if (kind === 'host') {
    const inMaint = !!node.maintenance
    items = [
      { label: 'Create VM…', icon: Plus, onClick: () => onAction('__create_vm__', node), show: true },
      { divider: true },
      inMaint
        ? { label: 'Exit Maintenance Mode', icon: Wrench, onClick: () => onAction('exit_maintenance', { host_id: node.id }), show: true, disabled: acting }
        : { label: 'Enter Maintenance Mode', icon: Wrench, onClick: () => onAction('enter_maintenance', { host_id: node.id }), show: true, disabled: acting },
      { label: node.status === 'connected' ? 'Disconnect Host' : 'Reconnect Host', icon: RefreshCw, onClick: () => onAction('reconnect_host', { host_id: node.id }), show: node.status !== 'connected', disabled: acting },
      { label: `${node.ssh_enabled ? 'Disable' : 'Enable'} SSH`, icon: Terminal, onClick: () => onAction('toggle_ssh', { host_id: node.id }), show: true, disabled: acting },
      { divider: true },
      { label: 'Add Networking — vSwitch…', icon: Network, onClick: () => onAction('__create_vswitch__', node), show: true },
      { label: 'Add Networking — Port Group…', icon: Network, onClick: () => onAction('__create_portgroup__', node), show: true },
      { label: 'New Datastore…', icon: Database, onClick: () => onAction('__create_datastore__', node), show: true },
      { divider: true },
      { label: 'Rescan Storage', icon: RefreshCw, onClick: () => onAction('rescan_hba', { host_id: node.id }), show: true, disabled: acting },
    ]
  } else if (kind === 'datastore') {
    items = [
      { label: 'Browse Files', icon: FolderOpen, onClick: () => onAction('__browse_ds__', node), show: true },
      { label: 'Increase Capacity (+500 GB)', icon: Plus, onClick: () => onAction('expand_datastore', { datastore: node.name, gb: 500 }), show: true, disabled: acting },
      { divider: true },
      { label: 'New Datastore…', icon: Database, onClick: () => onAction('__create_datastore__', node), show: true },
      { label: 'Remove Datastore', icon: Trash2, onClick: () => onAction('remove_datastore', { datastore_id: node.id }), show: true, disabled: acting, color: '#D9534F' },
    ]
  } else if (kind === 'network') {
    items = [
      { label: 'Edit Settings', icon: Settings, onClick: () => onAction('__net_edit__', node), show: true },
      { divider: true },
      { label: 'New Port Group / VLAN…', icon: Network, onClick: () => onAction('__create_portgroup__', node), show: true },
      { label: 'New vSwitch…', icon: Server, onClick: () => onAction('__create_vswitch__', node), show: true },
      { divider: true },
      { label: 'Remove Port Group', icon: Trash2, onClick: () => onAction('remove_portgroup', { network_id: node.id }), show: true, disabled: acting, color: '#D9534F' },
    ]
  }

  items = items.filter(i => i.divider || i.show)

  return (
    <>
      <div className="fixed inset-0 z-[79]" onClick={onClose} onContextMenu={e => { e.preventDefault(); onClose() }} />
      <div className="fixed z-[80] min-w-[208px] max-h-[80vh] overflow-y-auto bg-[#243447] border border-[#2D3A4A] rounded-[7px] shadow-2xl py-1 animate-[vmScale_0.12s_both]" style={{ left: x, top: y }}>
        <p className="text-[10px] font-bold text-[#8FA5B8] uppercase tracking-wide px-2.5 py-1.5 m-0 truncate">{title}</p>
        {items.map((item, i) => item.divider ? (
          <div key={`d-${i}`} className="h-px bg-[#2D3A4A] my-1" />
        ) : (
          <button
            key={item.label}
            type="button"
            disabled={item.disabled}
            onClick={() => { item.onClick(); if (!item.label.includes('…')) onClose() }}
            className="w-full flex items-center gap-2 px-2.5 py-1.5 text-left text-xs hover:bg-[#2D4057] disabled:opacity-40"
            style={{ color: item.color || '#E8EDF2' }}
          >
            <item.icon size={14} /> {item.label}
          </button>
        ))}
      </div>
    </>
  )
}
