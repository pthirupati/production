import {
  Terminal, SquareTerminal, GitBranch, Container, ShipWheel, Boxes, Hammer,
  Database, FileCode, FileCode2, Coffee, Binary,
} from 'lucide-react'

// Map the backend's icon string to a lucide component. Falls back to Terminal.
const ICONS = {
  terminal: Terminal,
  'square-terminal': SquareTerminal,
  'git-branch': GitBranch,
  container: Container,
  'ship-wheel': ShipWheel,
  boxes: Boxes,
  hammer: Hammer,
  database: Database,
  'file-code': FileCode,
  'file-code-2': FileCode2,
  coffee: Coffee,
  binary: Binary,
}

export function PlaygroundIcon({ name, ...props }) {
  const Cmp = ICONS[name] || Terminal
  return <Cmp {...props} />
}

export const CATEGORY_ORDER = [
  'Operating Systems',
  'Programming',
  'Databases',
  'Containers',
  'DevOps',
]
