import { useState } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'

/**
 * Nested sidebar navigation.
 * sections: [{ key, label, icon?, items?: [{ key, label, icon? }] }]
 */
export default function SimSidebar({
  sections = [], activeKey, onSelect, className = '', accent = '#5c4ee5',
}) {
  const [open, setOpen] = useState(() => Object.fromEntries(sections.map((s) => [s.key, true])))

  return (
    <nav className={`sim-sidebar shrink-0 overflow-y-auto ${className}`.trim()}>
      {sections.map((section) => {
        const hasChildren = section.items?.length > 0
        const isOpen = open[section.key] !== false
        const sectionActive = section.key === activeKey || section.items?.some((i) => i.key === activeKey)

        if (!hasChildren) {
          return (
            <button key={section.key} type="button" onClick={() => onSelect(section.key)}
              className={`sim-sidebar-item w-full flex items-center gap-2 px-3 py-2 text-left text-sm ${activeKey === section.key ? 'sim-sidebar-active' : ''}`}
              style={activeKey === section.key ? { borderLeftColor: accent } : undefined}>
              {section.icon && <section.icon size={15} className="shrink-0 opacity-80" />}
              <span className="truncate">{section.label}</span>
            </button>
          )
        }

        return (
          <div key={section.key} className="mb-0.5">
            <button type="button"
              onClick={() => setOpen((p) => ({ ...p, [section.key]: !isOpen }))}
              className={`w-full flex items-center gap-1 px-3 py-2 text-[11px] uppercase tracking-wide font-semibold text-slate-500 hover:text-slate-300 ${sectionActive ? 'text-slate-300' : ''}`}>
              {isOpen ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
              {section.label}
            </button>
            {isOpen && section.items.map((item) => (
              <button key={item.key} type="button" onClick={() => onSelect(item.key)}
                className={`sim-sidebar-item w-full flex items-center gap-2 pl-7 pr-3 py-2 text-left text-sm ${activeKey === item.key ? 'sim-sidebar-active' : ''}`}
                style={activeKey === item.key ? { borderLeftColor: accent } : undefined}>
                {item.icon && <item.icon size={14} className="shrink-0 opacity-75" />}
                <span className="truncate">{item.label}</span>
              </button>
            ))}
          </div>
        )
      })}
    </nav>
  )
}
