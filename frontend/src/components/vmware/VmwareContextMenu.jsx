import { Power, Camera, Copy, Settings, Trash2, Terminal, Pause, ArrowRightLeft, Pencil } from 'lucide-react'

export default function VmwareContextMenu({ x, y, vm, onClose, onAction, onConsole, acting }) {
  if (!vm) return null
  const isOn = vm.power === 'poweredOn'
  const isOff = vm.power === 'poweredOff'

  const items = [
    { label: 'Open console', icon: Terminal, onClick: () => { onConsole(vm); onClose() }, show: true },
    { divider: true },
    { label: 'Power On', icon: Power, onClick: () => onAction('power_on', { vm_id: vm.id }), show: isOff, disabled: acting },
    { label: 'Power Off', icon: Power, onClick: () => onAction('power_off', { vm_id: vm.id }), show: isOn, disabled: acting, color: '#D9534F' },
    { label: 'Suspend', icon: Pause, onClick: () => onAction('__suspend__', vm), show: isOn, disabled: acting },
    { label: 'Reset', icon: Power, onClick: () => onAction('reboot', { vm_id: vm.id }), show: isOn, disabled: acting },
    { divider: true },
    { label: 'Take Snapshot', icon: Camera, onClick: () => onAction('__snapshot__', vm), show: true },
    { label: 'Clone…', icon: Copy, onClick: () => onAction('__clone__', vm), show: true },
    { label: 'Migrate…', icon: ArrowRightLeft, onClick: () => onAction('__migrate__', vm), show: true },
    { label: 'Edit Settings…', icon: Settings, onClick: () => onAction('__edit__', vm), show: true },
    { label: 'Rename…', icon: Pencil, onClick: () => onAction('__rename__', vm), show: true },
    { divider: true },
    { label: 'Delete from Disk', icon: Trash2, onClick: () => onAction('__delete__', vm), show: !isOn, disabled: acting, color: '#D9534F' },
  ].filter(i => i.divider || i.show)

  return (
    <>
      <div className="fixed inset-0 z-[79]" onClick={onClose} onContextMenu={e => { e.preventDefault(); onClose() }} />
      <div className="fixed z-[80] min-w-[184px] bg-[#243447] border border-[#2D3A4A] rounded-[7px] shadow-2xl py-1 animate-[vmScale_0.12s_both]" style={{ left: x, top: y }}>
        <p className="text-[10px] font-bold text-[#8FA5B8] uppercase tracking-wide px-2.5 py-1.5 m-0">{vm.name}</p>
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
