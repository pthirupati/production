import { useState, useEffect, useMemo, useRef } from 'react'
import { Search } from 'lucide-react'
import { useModalA11y } from '../ConfirmModal'

/**
 * Fuzzy subsequence match, VS Code style: "nf" matches "New File".
 *
 * Returns a score (lower = better) or -1 for no match. Contiguous runs and
 * word-start hits score better so exact prefixes beat scattered letters.
 */
export function fuzzyScore(haystack, needle) {
  const hay = String(haystack ?? '')
  const pin = String(needle ?? '').trim()
  if (!pin) return 0
  const h = hay.toLowerCase()
  const n = pin.toLowerCase()
  let score = 0
  let hi = 0
  let lastHit = -1
  for (let ni = 0; ni < n.length; ni += 1) {
    const ch = n[ni]
    if (ch === ' ') continue
    const found = h.indexOf(ch, hi)
    if (found === -1) return -1
    // Penalise gaps; reward adjacency and matches at a word boundary.
    if (lastHit !== -1 && found !== lastHit + 1) score += found - lastHit
    const atWordStart = found === 0 || /[\s\-_/.]/.test(h[found - 1])
    if (!atWordStart) score += 1
    lastHit = found
    hi = found + 1
  }
  return score
}

/** Rank commands against a query, dropping non-matches. */
export function rankCommands(commands, query) {
  const q = String(query ?? '').trim()
  return (commands || [])
    .filter((c) => !c.hidden)
    .map((c) => ({ cmd: c, score: fuzzyScore(`${c.label} ${c.group || ''}`, q) }))
    .filter((r) => r.score >= 0)
    .sort((a, b) => a.score - b.score)
    .map((r) => r.cmd)
}

/**
 * Ctrl/Cmd+Shift+P command palette for the coding IDE.
 *
 * Commands carry their own `disabled` flag, mirroring the toolbar buttons they
 * duplicate. A disabled command stays VISIBLE but is not runnable — a palette
 * that quietly skipped those guards would let a learner mutate files after the
 * lab is solved, which the toolbar explicitly prevents.
 */
export default function CommandPalette({ open, commands, onClose }) {
  const [query, setQuery] = useState('')
  const [active, setActive] = useState(0)
  const inputRef = useRef(null)
  const listRef = useRef(null)
  const dialogRef = useModalA11y(open, onClose)

  const results = useMemo(() => rankCommands(commands, query), [commands, query])

  useEffect(() => {
    if (!open) return
    setQuery('')
    setActive(0)
    // Prefer the search input over the first focusable (backdrop is outside the panel).
    const id = setTimeout(() => inputRef.current?.focus(), 0)
    return () => clearTimeout(id)
  }, [open])

  useEffect(() => { setActive(0) }, [query])

  // Keep the highlighted row in view when arrowing past the fold.
  useEffect(() => {
    if (!open) return
    const el = listRef.current?.querySelector('[data-active="true"]')
    // Feature-detected: scrollIntoView is absent in jsdom and non-essential
    // here, so a missing implementation must not break palette navigation.
    if (typeof el?.scrollIntoView === 'function') el.scrollIntoView({ block: 'nearest' })
  }, [active, open])

  if (!open) return null

  const run = (cmd) => {
    if (!cmd || cmd.disabled) return
    onClose?.()
    cmd.run?.()
  }

  const onKeyDown = (e) => {
    if (e.key === 'Escape') { e.preventDefault(); onClose?.(); return }
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setActive((i) => (results.length ? (i + 1) % results.length : 0))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActive((i) => (results.length ? (i - 1 + results.length) % results.length : 0))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      run(results[active])
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-[12vh] px-4">
      <button
        type="button"
        aria-label="Close command palette"
        className="absolute inset-0 bg-black/50"
        onClick={() => onClose?.()}
      />
      <div
        ref={dialogRef}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-label="Command palette"
        className="relative w-full max-w-lg rounded-lg border border-[var(--vsc-border,#333)] bg-[var(--vsc-panel-bg,#252526)] shadow-2xl overflow-hidden outline-none"
      >
        <div className="flex items-center gap-2 px-3 py-2 border-b border-[var(--vsc-border,#333)]">
          <Search size={13} className="text-[var(--vsc-muted)] shrink-0" />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder="Type a command…"
            aria-label="Command"
            className="flex-1 bg-transparent outline-none text-sm text-[var(--vsc-text,#ccc)] placeholder:text-[var(--vsc-muted)]"
          />
        </div>
        <div ref={listRef} className="max-h-72 overflow-y-auto py-1">
          {!results.length && (
            <p className="px-3 py-3 text-xs text-[var(--vsc-muted)]">No matching commands.</p>
          )}
          {results.map((c, i) => (
            <button
              key={c.id}
              type="button"
              data-active={i === active}
              disabled={c.disabled}
              onMouseEnter={() => setActive(i)}
              onClick={() => run(c)}
              className={`w-full flex items-center justify-between gap-3 px-3 py-1.5 text-left text-xs ${
                i === active ? 'bg-[var(--vsc-accent,#0e639c)]/25' : ''
              } ${c.disabled ? 'opacity-40 cursor-not-allowed' : 'text-[var(--vsc-text,#ccc)]'}`}
            >
              <span className="truncate">
                {c.group && <span className="text-[var(--vsc-muted)]">{c.group}: </span>}
                {c.label}
              </span>
              {c.hint && <span className="text-[10px] text-[var(--vsc-muted)] shrink-0 font-mono">{c.hint}</span>}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
