import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const root = path.join(__dirname, '../node_modules/lucide-react/dist/esm/icons')
const dest = path.join(__dirname, '../src/ui/eagerIcons.jsx')

const nameMap = {
  activity: 'Activity',
  'alert-circle': 'AlertCircle',
  'alert-triangle': 'AlertTriangle',
  'arrow-left': 'ArrowLeft',
  'arrow-right': 'ArrowRight',
  'arrow-up': 'ArrowUp',
  award: 'Award',
  'bar-chart-3': 'BarChart3',
  bell: 'Bell',
  'book-open': 'BookOpen',
  bookmark: 'Bookmark',
  bot: 'Bot',
  boxes: 'Boxes',
  briefcase: 'Briefcase',
  'building-2': 'Building2',
  cable: 'Cable',
  check: 'Check',
  'check-check': 'CheckCheck',
  'check-circle-2': 'CheckCircle2',
  'chevron-right': 'ChevronRight',
  clock: 'Clock',
  cloud: 'Cloud',
  cpu: 'Cpu',
  'credit-card': 'CreditCard',
  eye: 'Eye',
  'eye-off': 'EyeOff',
  'file-text': 'FileText',
  filter: 'Filter',
  'folder-kanban': 'FolderKanban',
  gauge: 'Gauge',
  history: 'History',
  home: 'Home',
  layers: 'Layers',
  'layout-dashboard': 'LayoutDashboard',
  'life-buoy': 'LifeBuoy',
  'line-chart': 'LineChart',
  'loader-2': 'Loader2',
  lock: 'Lock',
  'log-out': 'LogOut',
  mail: 'Mail',
  megaphone: 'Megaphone',
  menu: 'Menu',
  'message-circle': 'MessageCircle',
  'message-square': 'MessageSquare',
  'mic-2': 'Mic2',
  'minimize-2': 'Minimize2',
  monitor: 'Monitor',
  'monitor-play': 'MonitorPlay',
  moon: 'Moon',
  phone: 'Phone',
  play: 'Play',
  'refresh-cw': 'RefreshCw',
  'rotate-ccw': 'RotateCcw',
  route: 'Route',
  'scroll-text': 'ScrollText',
  search: 'Search',
  send: 'Send',
  server: 'Server',
  shield: 'Shield',
  'shield-alert': 'ShieldAlert',
  'shield-check': 'ShieldCheck',
  skull: 'Skull',
  sparkles: 'Sparkles',
  star: 'Star',
  sun: 'Sun',
  tag: 'Tag',
  target: 'Target',
  terminal: 'Terminal',
  thermometer: 'Thermometer',
  'thumbs-down': 'ThumbsDown',
  'thumbs-up': 'ThumbsUp',
  ticket: 'Ticket',
  'trash-2': 'Trash2',
  trophy: 'Trophy',
  user: 'User',
  users: 'Users',
  'wifi-off': 'WifiOff',
  wrench: 'Wrench',
  x: 'X',
  zap: 'Zap',
}

function extractArray(text) {
  const marker = 'const __iconNode = '
  const start = text.indexOf(marker)
  if (start < 0) throw new Error('no __iconNode')
  let i = text.indexOf('[', start)
  let depth = 0
  for (let j = i; j < text.length; j++) {
    const c = text[j]
    if (c === '[') depth++
    else if (c === ']') {
      depth--
      if (depth === 0) return text.slice(i, j + 1)
    }
  }
  throw new Error('unbalanced')
}

const out = {}
for (const [kebab, pas] of Object.entries(nameMap)) {
  let fp = path.join(root, `${kebab}.js`)
  if (!fs.existsSync(fp)) throw new Error(`missing ${fp}`)
  let text = fs.readFileSync(fp, 'utf8')
  // Deprecated aliases re-export the renamed icon file.
  const re = text.match(/export\s*\{\s*default\s*\}\s*from\s*['"]\.\/([^'"]+)['"]/)
  if (re) {
    fp = path.join(root, re[1].endsWith('.js') ? re[1] : `${re[1]}.js`)
    text = fs.readFileSync(fp, 'utf8')
  }
  out[pas] = Function(`return (${extractArray(text)})`)()
}

const lines = [`/** Tiny SVG icon set for the eager entry graph.
 * Do NOT import lucide-react from modules reachable from main.jsx —
 * that pulls the whole \`icons\` manual chunk (~155kB gzip) onto first paint.
 * Paths copied from lucide-react v0.577.0 (ISC).
 * Regenerate: node frontend/scripts/gen-eager-icons.mjs
 */
import { forwardRef } from 'react'

function createIcon(name, children) {
  const Icon = forwardRef(function Icon(
    { size = 24, color = 'currentColor', strokeWidth = 2, className, ...props },
    ref,
  ) {
    return (
      <svg
        ref={ref}
        xmlns="http://www.w3.org/2000/svg"
        width={size}
        height={size}
        viewBox="0 0 24 24"
        fill="none"
        stroke={color}
        strokeWidth={strokeWidth}
        strokeLinecap="round"
        strokeLinejoin="round"
        className={className}
        aria-hidden={props['aria-hidden'] ?? true}
        {...props}
      >
        {children}
      </svg>
    )
  })
  Icon.displayName = name
  return Icon
}
`]

for (const [pas, nodes] of Object.entries(out)) {
  const kids = nodes.map(([tag, attrs]) => {
    const bits = Object.entries(attrs).map(([k, v]) => {
      if (typeof v === 'number') return `${k}={${v}}`
      return `${k}=${JSON.stringify(v)}`
    })
    return `    <${tag} ${bits.join(' ')} />`
  })
  lines.push(`export const ${pas} = createIcon('${pas}', (`)
  lines.push('  <>')
  lines.push(...kids)
  lines.push('  </>')
  lines.push('))')
  lines.push('')
}

fs.writeFileSync(dest, `${lines.join('\n')}\n`)
console.log('wrote', dest, fs.statSync(dest).size, 'icons', Object.keys(out).length)
