import { ExternalLink, Terminal } from 'lucide-react'

/**
 * Always-on companion console chips above fullscreen overlays (z-90).
 * LabRunner terminal strips sit under companion GUIs — without this strip,
 * Open AWX / MAAS / VyOS / LXD / Packer / Datacenter disappear when a tool opens.
 */
export default function CompanionToolStrip({
  chips = [],
  activeKind = null,
  onOpen,
  className = '',
}) {
  if (!chips.length) return null

  const btn = (kind, label, style, title, Icon = ExternalLink) => (
    <button
      key={kind}
      type="button"
      onClick={() => onOpen?.(kind)}
      title={title}
      className={`inline-flex items-center gap-1 px-2 py-1 rounded-md border text-[10px] font-semibold transition-opacity ${
        activeKind === kind ? 'ring-1 ring-white/40 opacity-100' : 'opacity-90 hover:opacity-100'
      }`}
      style={style}
    >
      <Icon size={11} /> {label}
    </button>
  )

  const styles = {
    awx: { borderColor: 'rgba(238,0,0,.45)', color: '#ff6b6b', background: 'rgba(238,0,0,.14)' },
    baremetal: { borderColor: 'rgba(13,148,136,.45)', color: '#2dd4bf', background: 'rgba(13,148,136,.14)' },
    lxd: { borderColor: 'rgba(233,84,32,.45)', color: '#E95420', background: 'rgba(233,84,32,.14)' },
    vyos: { borderColor: 'rgba(234,179,8,.45)', color: '#facc15', background: 'rgba(234,179,8,.14)' },
    packer: { borderColor: 'rgba(2,168,239,.45)', color: '#02A8EF', background: 'rgba(2,168,239,.14)' },
    datacenter: { borderColor: 'rgba(249,115,22,.5)', color: '#fb923c', background: 'rgba(249,115,22,.14)' },
    terraform: { borderColor: 'rgba(124,58,237,.45)', color: '#a78bfa', background: 'rgba(124,58,237,.14)' },
    aws: { borderColor: 'rgba(255,153,0,.5)', color: '#ff9900', background: 'rgba(255,153,0,.12)' },
    azure: { borderColor: 'rgba(0,120,212,.5)', color: '#50e6ff', background: 'rgba(0,120,212,.12)' },
    gcp: { borderColor: 'rgba(66,133,244,.5)', color: '#8ab4f8', background: 'rgba(66,133,244,.12)' },
  }

  const meta = {
    awx: ['Open AWX', 'Ansible Automation Controller'],
    baremetal: ['Open MAAS', 'MAAS — enlist / commission / deploy (VyOS PXE, LXD, AWX, Datacenter)'],
    lxd: ['Open LXD', 'LXD instances, profiles, storage, cluster'],
    vyos: ['Open VyOS', 'VyOS underlay — configure / commit for MAAS PXE'],
    packer: ['Open Packer', 'Packer Image Factory workspace'],
    datacenter: ['Open Datacenter', 'Datacenter twin — racks, BMC, power'],
    terraform: ['Open Terraform', 'Terraform workspace IDE'],
    aws: ['Open AWS', 'AWS Console'],
    azure: ['Open Azure', 'Azure Portal'],
    gcp: ['Open GCP', 'GCP Console'],
  }

  return (
    <div
      className={`fixed bottom-3 left-1/2 -translate-x-1/2 z-[90] max-w-[96vw] flex flex-wrap items-center justify-center gap-1.5 px-2.5 py-1.5 rounded-xl border border-white/10 shadow-lg pointer-events-auto ${className}`}
      style={{
        background: 'rgba(10,14,22,.92)',
        backdropFilter: 'blur(8px)',
      }}
      role="toolbar"
      aria-label="Lab companion tools"
    >
      <span className="text-[9px] uppercase tracking-wider text-surface-400 font-semibold px-1 mr-0.5">
        Lab tools
      </span>
      {chips.map((kind) => {
        const [label, title] = meta[kind] || [kind, kind]
        const Icon = kind === 'vyos' ? Terminal : ExternalLink
        return btn(kind, label, styles[kind] || styles.baremetal, title, Icon)
      })}
    </div>
  )
}
