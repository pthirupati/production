/** ANSI-ish colored log output for simulators. */
const ANSI = {
  '\x1b[32m': 'text-emerald-400',
  '\x1b[31m': 'text-red-400',
  '\x1b[33m': 'text-amber-300',
  '\x1b[36m': 'text-cyan-300',
  '\x1b[1m': 'font-bold',
  '\x1b[0m': '',
}

function parseLine(line) {
  const parts = []
  let rest = line
  while (rest.length) {
    const m = rest.match(/\x1b\[[0-9;]*m/)
    if (!m) {
      parts.push({ text: rest, cls: '' })
      break
    }
    const idx = m.index
    if (idx > 0) parts.push({ text: rest.slice(0, idx), cls: parts.at(-1)?.cls || '' })
    const code = m[0]
    rest = rest.slice(idx + code.length)
    const cls = ANSI[code] || (code === '\x1b[0m' ? '' : parts.at(-1)?.cls || '')
    if (code === '\x1b[0m') parts.push({ text: '', cls: '' })
    else parts.push({ text: '', cls })
    parts[parts.length - 1].pendingCls = cls
  }
  return parts.filter((p) => p.text)
}

export default function SimTerminalLog({ lines = [], className = '', title = 'Output' }) {
  const rows = Array.isArray(lines) ? lines : String(lines || '').split('\n')
  return (
    <div className={`sim-terminal-log flex flex-col min-h-0 ${className}`.trim()}>
      {title && (
        <div className="px-3 py-1.5 text-[10px] uppercase tracking-wide text-slate-500 border-b border-slate-800 bg-[#0d0d0d] shrink-0">
          {title}
        </div>
      )}
      <pre className="flex-1 min-h-[140px] overflow-auto p-3 text-[11px] font-mono leading-relaxed bg-[#0a0a0a] text-slate-300 m-0">
        {rows.map((line, i) => (
          <div key={i} className="whitespace-pre-wrap break-all">
            {line.includes('\x1b[') ? (
              parseLine(line).map((p, j) => <span key={j} className={p.cls}>{p.text}</span>)
            ) : line}
          </div>
        ))}
      </pre>
    </div>
  )
}
