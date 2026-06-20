import { useState } from 'react'
import {
  Power, Camera, Copy, Settings, Trash2, Terminal, Pause, ArrowRightLeft, Pencil,
  HardDrive, Network, Wrench, RefreshCw, Plus, FolderOpen, Database, Server,
  Tag, ShieldCheck, Bell, Folder, Boxes, Layers, Move, ChevronRight, Cloud, FileText,
} from 'lucide-react'
import { buildVmMenu, buildHostMenu, buildDatacenterMenu } from './vmwareMenus'

const ICONS = {
  Power, Camera, Copy, Settings, Trash2, Terminal, Pause, ArrowRightLeft, Pencil,
  HardDrive, Network, Wrench, RefreshCw, Plus, FolderOpen, Database, Server,
  Tag, ShieldCheck, Bell, Folder, Boxes, Layers, Move, Cloud, FileText,
}

/* Renders the SAME menu trees as the right-click context menu, but as the
   object-bar "Actions ▾" dropdown. Submenus open to the left (flyout). */
function Items({ items, onClose }) {
  const [openSub, setOpenSub] = useState(null)
  return (
    <>
      {items.map((item, i) => {
        if (item.divider) return <div key={`d-${i}`} className="h-px bg-[#2D3A4A] my-1" />
        if (item.hidden) return null
        const Icon = item.icon ? ICONS[item.icon] : null
        if (item.children) {
          return (
            <div key={item.label} className="relative" onMouseEnter={() => setOpenSub(i)} onMouseLeave={() => setOpenSub(null)}>
              <button type="button" className="w-full flex items-center gap-2 px-3 py-1.5 text-left text-[12px] hover:bg-[#2d4057] rounded" style={{ color: item.color || '#e8edf2' }}>
                {Icon && <Icon size={14} />}<span className="flex-1">{item.label}</span><ChevronRight size={13} className="text-[#8FA5B8]" />
              </button>
              {openSub === i && (
                <div className="absolute top-0 right-full -mr-1 min-w-[220px] bg-[#243447] border border-[#2D3A4A] rounded-[7px] shadow-2xl py-1 z-[73] animate-[vmScale_0.12s_both]">
                  <Items items={item.children} onClose={onClose} />
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
            className="w-full flex items-center gap-2 px-3 py-1.5 text-left text-[12px] hover:bg-[#2d4057] disabled:opacity-40 disabled:cursor-not-allowed rounded"
            style={{ color: item.color || '#e8edf2' }}
          >
            {Icon && <Icon size={14} />}<span className="flex-1">{item.label}</span>
          </button>
        )
      })}
    </>
  )
}

export default function VmwareActionsMenu({ kind, target, onAction, onConsole, onClose, acting }) {
  if (!target) return null
  let items = []
  if (kind === 'vm') items = buildVmMenu(target, onAction, onConsole, onClose, acting)
  else if (kind === 'host') items = buildHostMenu(target, onAction, acting)
  else if (kind === 'datacenter') items = buildDatacenterMenu(target, onAction, acting)
  else return null

  return (
    <div className="vm-actions-menu">
      <Items items={items} onClose={onClose} />
    </div>
  )
}
