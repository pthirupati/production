import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, Navigate, useParams } from 'react-router-dom'
import { ChevronLeft, Play, RotateCcw, Terminal, Database, Code2 } from 'lucide-react'
import PublicLayout from '../../components/layout/PublicLayout'
import { FixitPanel } from '../../components/design'
import { usePageTitle } from '../../hooks/usePageTitle'
import { playgroundApi } from '../../api/playgrounds'
import { tutorialPlaygroundHref } from '../../utils/playgroundLinks'

const KIND_ICON = {
  terminal: Terminal,
  sql: Database,
  code: Code2,
  lab_link: Play,
}

export default function PlaygroundDetail() {
  const { slug } = useParams()
  const [pg, setPg] = useState(null)
  const [loading, setLoading] = useState(true)
  const [notFound, setNotFound] = useState(false)
  const sessionRef = useRef(playgroundApi.newSessionId())
  const [input, setInput] = useState('')
  const [output, setOutput] = useState('')
  const [busy, setBusy] = useState(false)

  usePageTitle(pg?.name || 'Playground', pg?.tagline || '')

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setNotFound(false)
    playgroundApi.detail(slug)
      .then((data) => {
        if (cancelled) return
        if (!data || data.error) { setNotFound(true); return }
        setPg(data)
        if (data.kind === 'code' && data.starter_code) setInput(data.starter_code)
      })
      .catch(() => { if (!cancelled) setNotFound(true) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [slug])

  const Icon = KIND_ICON[pg?.kind] || Terminal

  const run = async (cmd) => {
    if (!pg || busy) return
    setBusy(true)
    try {
      const payload = pg.kind === 'code'
        ? { session: sessionRef.current, input: cmd ?? input }
        : { session: sessionRef.current, input: cmd ?? input }
      const res = await playgroundApi.run(slug, payload)
      const text = res.output || res.error || res.message || JSON.stringify(res, null, 2)
      setOutput((prev) => `${prev}${prev ? '\n' : ''}${text}`.slice(-120000))
    } catch {
      setOutput((prev) => `${prev}${prev ? '\n' : ''}[error] Could not run — try again.`)
    } finally {
      setBusy(false)
    }
  }

  const reset = async () => {
    sessionRef.current = playgroundApi.newSessionId()
    setOutput('')
    if (pg?.starter_code) setInput(pg.starter_code)
    await playgroundApi.reset(slug, sessionRef.current)
  }

  const starters = useMemo(() => pg?.starter || [], [pg])

  if (loading) {
    return (
      <PublicLayout>
        <div className="max-w-4xl mx-auto px-4 py-16 animate-pulse">
          <div className="h-8 w-1/2 bg-surface-800 rounded mb-4" />
          <div className="h-64 bg-surface-900 rounded" />
        </div>
      </PublicLayout>
    )
  }

  if (notFound || !pg) {
    return (
      <PublicLayout>
        <div className="max-w-xl mx-auto px-4 py-24 text-center">
          <p className="text-surface-400 mb-4">Playground not found.</p>
          <Link to="/playgrounds" className="btn-secondary text-sm">All playgrounds</Link>
        </div>
      </PublicLayout>
    )
  }

  if (pg.kind === 'lab_link') {
    const to = pg.scenario_slug
      ? `/scenarios/${pg.scenario_slug}`
      : tutorialPlaygroundHref(slug)
    return <Navigate to={to} replace />
  }

  return (
    <PublicLayout>
      <div className="max-w-5xl mx-auto px-4 sm:px-6 py-10">
        <Link to="/playgrounds" className="inline-flex items-center gap-1.5 text-sm text-surface-400 hover:text-accent-cyan mb-6">
          <ChevronLeft size={15} /> All playgrounds
        </Link>

        <header className="mb-6">
          <div className="flex items-center gap-3 mb-2">
            <div className="w-11 h-11 rounded-xl bg-surface-800 border border-surface-700 flex items-center justify-center text-accent-cyan">
              <Icon size={22} />
            </div>
            <div>
              <h1 className="font-display text-2xl font-bold text-white">{pg.name}</h1>
              <p className="text-sm text-surface-400">{pg.tagline}</p>
            </div>
          </div>
          <p className="text-xs text-surface-500">
            Ephemeral sandbox — nothing is saved. Session resets after {Math.round((pg.idle_timeout_seconds || 900) / 60)} min idle.
          </p>
        </header>

        <FixitPanel padding="p-0" className="overflow-hidden mb-4">
          {pg.kind === 'code' ? (
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              spellCheck={false}
              className="w-full min-h-[220px] p-4 bg-surface-950 text-surface-100 font-mono text-sm border-0 outline-none resize-y"
              placeholder="# Write code here"
            />
          ) : (
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') run() }}
              className="w-full px-4 py-3 bg-surface-950 text-surface-100 font-mono text-sm border-0 border-b border-surface-800 outline-none"
              placeholder={pg.kind === 'sql' ? 'SELECT * FROM employees;' : '$ type a command and press Enter'}
            />
          )}
          <pre className="min-h-[240px] max-h-[420px] overflow-auto p-4 bg-surface-950/80 text-[13px] font-mono text-surface-200 whitespace-pre-wrap">
            {output || (pg.prompt ? `${pg.prompt}` : 'Output appears here…')}
          </pre>
        </FixitPanel>

        <div className="flex flex-wrap gap-2 mb-4">
          <button type="button" onClick={() => run()} disabled={busy} className="btn-primary text-sm inline-flex items-center gap-1.5 disabled:opacity-60">
            <Play size={14} /> {busy ? 'Running…' : 'Run'}
          </button>
          <button type="button" onClick={reset} className="btn-secondary text-sm inline-flex items-center gap-1.5">
            <RotateCcw size={14} /> Reset
          </button>
          {pg.technology_slug && (
            <Link to={`/technologies/${pg.technology_slug}`} className="btn-secondary text-sm ml-auto">
              Open full {pg.technology_slug} labs →
            </Link>
          )}
        </div>

        {starters.length > 0 && (
          <div className="flex flex-wrap gap-2">
            <span className="text-xs text-surface-500 w-full mb-1">Try:</span>
            {starters.map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => { setInput(s); run(s) }}
                className="text-xs font-mono px-2.5 py-1 rounded-lg bg-surface-800/80 border border-surface-700 text-surface-300 hover:border-accent-cyan/40 hover:text-accent-cyan transition-colors truncate max-w-full"
              >
                {s.length > 48 ? `${s.slice(0, 45)}…` : s}
              </button>
            ))}
          </div>
        )}
      </div>
    </PublicLayout>
  )
}
