import { useState } from 'react'
import {
  Power, Camera, Copy, Settings, Trash2, Terminal, Pause, ArrowRightLeft, Pencil,
  HardDrive, Network, Wrench, RefreshCw, Plus, FolderOpen, Database, Server,
  Tag, ShieldCheck, Bell, Folder, Boxes, Layers, Move, ChevronRight, Cloud, FileText,
} from 'lucide-react'

import { buildVmMenu, buildHostMenu, buildDatacenterMenu } from './vmwareMenus'

/* Full vSphere-style right-click menu with nested submenus. Supports VMs,
   hosts, datacenters, datastores and networks via the `kind` prop. `onAction`
   receives either a real engine action (e.g. 'power_on') or a UI sentinel
   (e.g. '__add_disk__') that the simulator maps to a modal/panel. */

const ICONS = {
  Power, Camera, Copy, Settings, Trash2, Terminal, Pause, ArrowRightLeft, Pencil,
  HardDrive, Network, Wrench, RefreshCw, Plus, FolderOpen, Database, Server,
  Tag, ShieldCheck, Bell, Folder, Boxes, Layers, Move, Cloud, FileText,
}

function MenuItems({ items, onClose, depth = 0 }) {
  const [openSub, setOpenSub] = useState(null)
  return (
    <>
      {items.map((item, i) => {
        if (item.divider) return <div key={`d-${i}`} className="h-px bg-[#2D3A4A] my-1" />
        if (item.hidden) return null
        const Icon = item.icon ? ICONS[item.icon] : null
        if (item.children) {
          return (
            <div
              key={item.label}
              className="relative"
              onMouseEnter={() => setOpenSub(i)}
              onMouseLeave={() => setOpenSub(null)}
            >
              <button
                type="button"
                className="w-full flex items-center gap-2 px-2.5 py-1.5 text-left text-xs hover:bg-[#2D4057]"
                style={{ color: item.color || '#E8EDF2' }}
              >
                {Icon && <Icon size={14} />}
                <span className="flex-1">{item.label}</span>
                <ChevronRight size={13} className="text-[#8FA5B8]" />
              </button>
              {openSub === i && (
                <div className="absolute top-0 left-full -ml-1 min-w-[220px] bg-[#243447] border border-[#2D3A4A] rounded-[7px] shadow-2xl py-1 z-[81] animate-[vmScale_0.12s_both]">
                  <MenuItems items={item.children} onClose={onClose} depth={depth + 1} />
                </div>
              )}
            </div>
          )
        }
        return (
          <button
            key={item.label}
            type="button"
            disabled={item.disabled}
            onClick={() => { item.onClick?.(); if (!item.keepOpen && !item.label.includes('…')) onClose() }}
            className="w-full flex items-center gap-2 px-2.5 py-1.5 text-left text-xs hover:bg-[#2D4057] disabled:opacity-40"
            style={{ color: item.color || '#E8EDF2' }}
          >
            {Icon && <Icon size={14} />}
            <span className="flex-1">{item.label}</span>
          </button>
        )
      })}
    </>
  )
}

export default function VmwareContextMenu({ x, y, kind = 'vm', vm, node, onClose, onAction, onConsole, acting }) {
  const target = vm || node
  if (!target) return null

  const title = target.name
  let items = []

  if (kind === 'vm') {
    items = buildVmMenu(vm, onAction, onConsole, onClose, acting)
  } else if (kind === 'host') {
    items = buildHostMenu(node, onAction, acting)
  } else if (kind === 'datacenter') {
    items = buildDatacenterMenu(node, onAction, acting)
  } else if (kind === 'datastore') {
    items = [
      { label: 'Browse Files', icon: 'FolderOpen', onClick: () => onAction('__browse_ds__', node) },
      { label: 'Increase Capacity (+500 GB)', icon: 'Plus', onClick: () => onAction('expand_datastore', { datastore: node.name, gb: 500 }), disabled: acting },
      { divider: true },
      { label: 'New Datastore…', icon: 'Database', onClick: () => onAction('__create_datastore__', node) },
      { label: 'New Datastore Cluster…', icon: 'Boxes', onClick: () => onAction('__create_datastore_cluster__', node) },
      { label: 'Rescan Storage', icon: 'RefreshCw', onClick: () => onAction('rescan_storage', {}), disabled: acting },
      { divider: true },
      { label: 'Rename…', icon: 'Pencil', onClick: () => onAction('__rename_ds__', node) },
      { label: 'Remove Datastore', icon: 'Trash2', onClick: () => onAction('remove_datastore', { datastore_id: node.id }), disabled: acting, color: '#D9534F' },
    ]
  } else if (kind === 'network') {
    items = [
      { label: 'Edit Settings', icon: 'Settings', onClick: () => onAction('__net_edit__', node) },
      { divider: true },
      { label: 'New Port Group / VLAN…', icon: 'Network', onClick: () => onAction('__create_portgroup__', node) },
      { label: 'New vSwitch…', icon: 'Server', onClick: () => onAction('__create_vswitch__', node) },
      { label: 'Migrate VMs to Another Network…', icon: 'ArrowRightLeft', onClick: () => onAction('__migrate_network__', node) },
      { divider: true },
      { label: 'Rename…', icon: 'Pencil', onClick: () => onAction('__rename_net__', node) },
      { label: 'Remove Port Group', icon: 'Trash2', onClick: () => onAction('remove_portgroup', { network_id: node.id }), disabled: acting, color: '#D9534F' },
    ]
  }

  return (
    <>
      <div className="fixed inset-0 z-[79]" onClick={onClose} onContextMenu={e => { e.preventDefault(); onClose() }} />
      <div className="fixed z-[80] min-w-[224px] max-h-[80vh] overflow-y-auto bg-[#243447] border border-[#2D3A4A] rounded-[7px] shadow-2xl py-1 animate-[vmScale_0.12s_both]" style={{ left: x, top: y }}>
        <p className="text-[10px] font-bold text-[#8FA5B8] uppercase tracking-wide px-2.5 py-1.5 m-0 truncate">{title}</p>
        <MenuItems items={items} onClose={onClose} />
      </div>
    </>
  )
}
