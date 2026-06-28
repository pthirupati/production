import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import {
  Clock, Layers, ChevronLeft, ChevronRight, FlaskConical,
  Copy, Check, BookOpen, ListTree, GraduationCap, Terminal,
} from 'lucide-react'
import PublicLayout from '../../components/layout/PublicLayout'
import { FixitPanel } from '../../components/design'
import { usePageTitle } from '../../hooks/usePageTitle'
import { tutorialApi } from '../../api/tutorials'
import { useAuthStore } from '../../store/authStore'
import TutorialQuiz from '../../components/tutorials/TutorialQuiz'
import { tutorialPlaygroundHref } from '../../utils/playgroundLinks'
import { getLocalTutorialProgress, markLocalSection, progressPct, setLocalTutorialProgress } from '../../utils/tutorialProgress'

const DIFFICULTY_CLASS = {
  beginner: 'text-accent-green bg-accent-green/10 border-accent-green/20',
  intermediate: 'text-accent-amber bg-accent-amber/10 border-accent-amber/20',
  advanced: 'text-accent-red bg-accent-red/10 border-accent-red/20',
  expert: 'text-pink-400 bg-pink-500/10 border-pink-500/20',
  enterprise: 'text-accent-purple bg-accent-purple/10 border-accent-purple/20',
}

function sectionTheme(heading) {
  const h = (heading || '').toLowerCase()
  if (h.includes('theory')) return 'tutorial-section-theory'
  if (h.includes('architecture')) return 'tutorial-section-architecture'
  if (h.includes('concept')) return 'tutorial-section-concepts'
  if (h.includes('lab') || h.includes('hands-on') || h.includes('simulation') || h.includes('project')) return 'tutorial-section-labs'
  if (h.includes('troubleshoot') || h.includes('incident') || h.includes('rca') || h.includes('root cause')) return 'tutorial-section-troubleshooting'
  if (h.includes('security')) return 'tutorial-section-security'
  if (h.includes('enterprise') || h.includes('production')) return 'tutorial-section-enterprise'
  if (h.includes('interview') || h.includes('scenario question') || h.includes('assessment') || h.includes('certification')) return 'tutorial-section-interview'
  if (h.includes('notes') || h.includes('takeaway')) return 'tutorial-section-notes'
  if (h.includes('monitor') || h.includes('performance')) return 'tutorial-section-monitoring'
  return 'tutorial-section-concepts'
}

const LEVEL_CLASS = {
  beginner: 'tutorial-level-beginner',
  intermediate: 'tutorial-level-intermediate',
  advanced: 'tutorial-level-advanced',
  expert: 'tutorial-level-expert',
  enterprise: 'tutorial-level-enterprise',
}

function formatInline(text) {
  // Tokenize **bold**, `inline code`, and [label](url) so commands/syntax in
  // prose render as real code chips and links instead of raw markdown.
  const tokens = []
  const regex = /(\*\*[^*]+\*\*|`[^`]+`|\[[^\]]+\]\([^)]+\))/g
  let lastIndex = 0
  let key = 0
  let m
  while ((m = regex.exec(text || '')) !== null) {
    if (m.index > lastIndex) tokens.push(text.slice(lastIndex, m.index))
    const tok = m[0]
    if (tok.startsWith('**')) {
      tokens.push(<strong key={key++}>{tok.slice(2, -2)}</strong>)
    } else if (tok.startsWith('`')) {
      tokens.push(<code key={key++} className="tutorial-inline-code">{tok.slice(1, -1)}</code>)
    } else {
      const lm = /\[([^\]]+)\]\(([^)]+)\)/.exec(tok)
      if (lm) {
        tokens.push(
          <a key={key++} href={lm[2]} target="_blank" rel="noopener noreferrer" className="tutorial-inline-link">
            {lm[1]}
          </a>,
        )
      }
    }
    lastIndex = regex.lastIndex
  }
  if (lastIndex < (text || '').length) tokens.push(text.slice(lastIndex))
  return tokens
}

/* Parse markdown-ish body into structured blocks so commands, numbered
   playbooks, fenced code, tables and callouts all render (not just bold +
   bullets). The backend already authors all of these — they were previously
   shown as raw text. */
function parseBlocks(text) {
  const lines = (text || '').split('\n')
  const blocks = []
  let i = 0
  const isTableRow = (l) => /^\s*\|.*\|\s*$/.test(l)
  const isTableSep = (l) => /^\s*\|?[\s:|-]+\|?\s*$/.test(l) && l.includes('-')
  while (i < lines.length) {
    const line = lines[i]
    const trimmed = line.trim()
    if (!trimmed) { i++; continue }

    // Fenced code block
    const fence = trimmed.match(/^```+\s*([a-zA-Z0-9_+-]*)\s*$/)
    if (fence) {
      const lang = fence[1] || 'text'
      const buf = []
      i++
      while (i < lines.length && !/^```+\s*$/.test(lines[i].trim())) { buf.push(lines[i]); i++ }
      i++ // skip closing fence
      blocks.push({ type: 'code', code: buf.join('\n'), lang })
      continue
    }

    // Horizontal rule
    if (/^(-{3,}|\*{3,}|_{3,})$/.test(trimmed)) { blocks.push({ type: 'hr' }); i++; continue }

    // Headings (##, ###, ####)
    const h = trimmed.match(/^(#{2,4})\s+(.*)$/)
    if (h) { blocks.push({ type: 'heading', level: h[1].length, text: h[2].trim() }); i++; continue }

    // Blockquote / callout
    if (trimmed.startsWith('> ')) {
      const buf = []
      while (i < lines.length && lines[i].trim().startsWith('> ')) { buf.push(lines[i].trim().slice(2)); i++ }
      blocks.push({ type: 'quote', text: buf.join(' ') })
      continue
    }

    // Table
    if (isTableRow(line) && i + 1 < lines.length && isTableSep(lines[i + 1])) {
      const parseRow = (l) => l.trim().replace(/^\||\|$/g, '').split('|').map((c) => c.trim())
      const header = parseRow(line)
      i += 2
      const rows = []
      while (i < lines.length && isTableRow(lines[i])) { rows.push(parseRow(lines[i])); i++ }
      blocks.push({ type: 'table', header, rows })
      continue
    }

    // Ordered list
    if (/^\s*\d+\.\s+/.test(line)) {
      const items = []
      while (i < lines.length && /^\s*\d+\.\s+/.test(lines[i])) { items.push(lines[i].replace(/^\s*\d+\.\s+/, '')); i++ }
      blocks.push({ type: 'ol', items })
      continue
    }

    // Unordered list
    if (/^\s*[-*]\s+/.test(line)) {
      const items = []
      while (i < lines.length && /^\s*[-*]\s+/.test(lines[i])) { items.push(lines[i].replace(/^\s*[-*]\s+/, '')); i++ }
      blocks.push({ type: 'ul', items })
      continue
    }

    // Paragraph (gather consecutive plain lines until a blank/structural line)
    const buf = [line]
    i++
    while (i < lines.length) {
      const nxt = lines[i]
      const nt = nxt.trim()
      if (!nt) break
      if (/^```+/.test(nt) || /^(#{2,4})\s+/.test(nt) || /^\s*\d+\.\s+/.test(nxt) || /^\s*[-*]\s+/.test(nxt) || nt.startsWith('> ') || isTableRow(nxt) || /^(-{3,}|\*{3,}|_{3,})$/.test(nt)) break
      buf.push(nxt)
      i++
    }
    blocks.push({ type: 'p', text: buf.join('\n') })
  }
  return blocks
}

function CodeBlock({ code, language, caption }) {
  const [copied, setCopied] = useState(false)
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(code)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch { /* clipboard unavailable */ }
  }
  return (
    <figure className="tutorial-code-block">
      <div className="tutorial-code-bar">
        <span className="tutorial-code-lang">{language || 'code'}</span>
        <button type="button" onClick={copy} className="tutorial-code-copy">
          {copied ? <Check size={12} className="text-accent-green" /> : <Copy size={12} />}
          {copied ? 'Copied' : 'Copy'}
        </button>
      </div>
      <pre className="tutorial-code-pre"><code>{code}</code></pre>
      {caption && <figcaption className="tutorial-code-caption">{caption}</figcaption>}
    </figure>
  )
}

function Body({ text }) {
  if (!text) return null
  const blocks = parseBlocks(text)
  return (
    <div className="tutorial-prose space-y-4">
      {blocks.map((b, i) => {
        switch (b.type) {
          case 'code':
            return <CodeBlock key={i} code={b.code} language={b.lang} />
          case 'hr':
            return <hr key={i} className="border-surface-800 my-2" />
          case 'heading': {
            const cls = b.level === 2
              ? 'text-lg font-semibold text-white tracking-tight'
              : b.level === 3
                ? 'text-base font-semibold text-surface-100 tracking-tight'
                : 'text-sm font-semibold text-surface-200 uppercase tracking-wide'
            return <h3 key={i} className={cls}>{formatInline(b.text)}</h3>
          }
          case 'quote':
            return (
              <blockquote key={i} className="tutorial-callout">
                {formatInline(b.text)}
              </blockquote>
            )
          case 'table':
            return (
              <div key={i} className="tutorial-table-wrap">
                <table className="tutorial-table">
                  <thead>
                    <tr>{b.header.map((c, j) => <th key={j}>{formatInline(c)}</th>)}</tr>
                  </thead>
                  <tbody>
                    {b.rows.map((row, r) => (
                      <tr key={r}>{row.map((c, j) => <td key={j}>{formatInline(c)}</td>)}</tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )
          case 'ol':
            return (
              <ol key={i} className="list-decimal pl-5 space-y-2 text-surface-300">
                {b.items.map((it, j) => <li key={j} className="leading-relaxed">{formatInline(it)}</li>)}
              </ol>
            )
          case 'ul':
            return (
              <ul key={i} className="list-disc pl-5 space-y-2 text-surface-300">
                {b.items.map((it, j) => <li key={j} className="leading-relaxed">{formatInline(it)}</li>)}
              </ul>
            )
          default:
            return <p key={i} className="whitespace-pre-line leading-relaxed">{formatInline(b.text)}</p>
        }
      })}
    </div>
  )
}

function SectionNav({ sections, activeOrder }) {
  return (
    <nav className="space-y-1">
      <p className="text-[10px] font-bold uppercase tracking-wider text-surface-500 mb-2 px-2">In this tutorial</p>
      {sections.map((s, i) => {
        const active = s.order === activeOrder
        return (
          <a
            key={s.order}
            href={`#section-${s.order}`}
            className={`tutorial-nav-link truncate ${active ? 'is-active' : ''}`}
          >
            <span className="font-mono text-[10px] opacity-60 mr-1.5">{String(i + 1).padStart(2, '0')}</span>
            {s.heading}
          </a>
        )
      })}
    </nav>
  )
}

export default function TutorialDetail() {
  const { slug } = useParams()
  const navigate = useNavigate()
  const { isAuthenticated } = useAuthStore()
  const [tutorial, setTutorial] = useState(null)
  const [loading, setLoading] = useState(true)
  const [notFound, setNotFound] = useState(false)
  const [activeSection, setActiveSection] = useState(null)
  const [completedSections, setCompletedSections] = useState([])
  const [readProgressPct, setReadProgressPct] = useState(0)

  usePageTitle(tutorial?.meta_title || 'Tutorial', tutorial?.meta_description || '')

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setNotFound(false)
    tutorialApi.detail(slug)
      .then((data) => {
        if (cancelled) return
        if (!data || data.error) { setNotFound(true); return }
        setTutorial(data)
        const prog = data.user_progress
        if (prog?.completed_sections) {
          setCompletedSections(prog.completed_sections)
          setReadProgressPct(prog.progress_pct || progressPct(prog.completed_sections, data.sections?.length))
        } else {
          const local = getLocalTutorialProgress(slug)
          setCompletedSections(local.completed_sections || [])
          setReadProgressPct(progressPct(local.completed_sections, data.sections?.length))
        }
      })
      .catch(() => { if (!cancelled) setNotFound(true) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [slug])

  const persistSectionProgress = (sectionOrder) => {
    if (!tutorial || !sectionOrder) return
    const total = tutorial.sections?.length || 0
    setCompletedSections((prev) => {
      if (prev.includes(sectionOrder)) return prev
      const next = [...prev, sectionOrder].sort((a, b) => a - b)
      setReadProgressPct(progressPct(next, total))
      if (isAuthenticated) {
        tutorialApi.updateProgress(slug, { section_order: sectionOrder, completed_sections: next }).catch(() => {})
      } else {
        markLocalSection(slug, sectionOrder, total)
      }
      return next
    })
  }

  const markTutorialComplete = () => {
    const total = tutorial.sections?.length || 0
    const allOrders = (tutorial.sections || []).map((s) => s.order)
    setCompletedSections(allOrders)
    setReadProgressPct(100)
    if (isAuthenticated) {
      tutorialApi.updateProgress(slug, { mark_complete: true, completed_sections: allOrders }).catch(() => {})
    } else {
      setLocalTutorialProgress(slug, { completed_sections: allOrders, completed: true, last_section_order: total })
    }
  }

  useEffect(() => {
    if (!tutorial?.seo_keywords) return
    let meta = document.querySelector('meta[name="keywords"]')
    if (!meta) {
      meta = document.createElement('meta')
      meta.name = 'keywords'
      document.head.appendChild(meta)
    }
    meta.content = tutorial.seo_keywords
  }, [tutorial])

  useEffect(() => {
    if (!tutorial?.sections?.length) return
    const obs = new IntersectionObserver(
      (entries) => {
        const visible = entries.filter((e) => e.isIntersecting).sort((a, b) => b.intersectionRatio - a.intersectionRatio)
        if (visible[0]?.target?.id) {
          const order = Number(visible[0].target.id.replace('section-', ''))
          if (!Number.isNaN(order)) {
            setActiveSection(order)
            persistSectionProgress(order)
          }
        }
      },
      { rootMargin: '-20% 0px -60% 0px', threshold: [0, 0.25, 0.5] },
    )
    tutorial.sections.forEach((s) => {
      const el = document.getElementById(`section-${s.order}`)
      if (el) obs.observe(el)
    })
    return () => obs.disconnect()
  }, [tutorial])

  if (loading) {
    return (
      <PublicLayout>
        <div className="tutorial-page max-w-6xl mx-auto px-4 py-16">
          <div className="h-8 w-2/3 bg-surface-800 rounded animate-pulse mb-4" />
          <div className="grid lg:grid-cols-[240px_1fr] gap-8">
            <div className="h-64 bg-surface-900 rounded-xl animate-pulse hidden lg:block" />
            <div className="space-y-4">
              <div className="h-4 w-full bg-surface-900 rounded animate-pulse" />
              <div className="h-4 w-5/6 bg-surface-900 rounded animate-pulse" />
            </div>
          </div>
        </div>
      </PublicLayout>
    )
  }

  if (notFound || !tutorial) {
    return (
      <PublicLayout>
        <div className="tutorial-page max-w-2xl mx-auto px-4 py-24 text-center">
          <BookOpen size={36} className="mx-auto mb-4 text-surface-500" />
          <h1 className="font-display text-2xl font-bold text-white mb-2">Tutorial not found</h1>
          <Link to="/tutorials" className="btn-primary text-sm">Back to all tutorials</Link>
        </div>
      </PublicLayout>
    )
  }

  const sections = tutorial.sections || []
  const curriculum = tutorial.curriculum || {}
  const hasScenario = Boolean(tutorial.scenario_slug || tutorial.linked_scenario)
  const linkedScenario = tutorial.linked_scenario
  const readingPct = readProgressPct || progressPct(completedSections, sections.length)
  const progressPctTrack = curriculum.total_in_topic
    ? Math.round((curriculum.position / curriculum.total_in_topic) * 100)
    : 0

  return (
    <PublicLayout>
      <div className="tutorial-page relative overflow-hidden min-h-screen">
        <div className="absolute inset-0 aurora-bg opacity-25 pointer-events-none" aria-hidden="true" />
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[300px] bg-accent-cyan/[0.04] blur-[100px] pointer-events-none" />

        <div className="relative max-w-6xl mx-auto px-4 sm:px-6 py-10">
          <div className="flex flex-wrap items-center gap-2 text-sm text-surface-500 mb-6">
            <Link to="/tutorials" className="hover:text-accent-cyan transition-colors">Tutorials</Link>
            <span>/</span>
            {tutorial.course_slug ? (
              <>
                <span className="text-surface-400">{tutorial.course_title || tutorial.course_slug}</span>
                <span>/</span>
              </>
            ) : (
              <>
                <Link to={`/tutorials?topic=${encodeURIComponent(tutorial.topic)}`} className="hover:text-accent-cyan transition-colors">
                  {tutorial.topic}
                </Link>
                <span>/</span>
              </>
            )}
            <span className="text-surface-300 truncate max-w-[200px]">{tutorial.title}</span>
          </div>

          <div className="grid lg:grid-cols-[260px_minmax(0,1fr)] gap-8 items-start">
            <aside className="hidden lg:block sticky top-24 space-y-6">
              <FixitPanel padding="p-4" className="border-accent-cyan/10">
                <div className="flex items-center gap-2 mb-3">
                  <GraduationCap size={16} className="text-accent-cyan" />
                  <p className="tutorial-sidebar-title">{curriculum.topic} path</p>
                </div>
                <p className="text-[10px] text-surface-500 mb-2">
                  Lesson {curriculum.position} of {curriculum.total_in_topic}
                </p>
                <div className="h-1.5 bg-surface-800 rounded-full overflow-hidden mb-1">
                  <div className="h-full bg-accent-cyan rounded-full transition-all" style={{ width: `${progressPctTrack}%` }} />
                </div>
                <p className="text-[10px] text-surface-500 mb-3">Reading progress: {readingPct}%</p>
                <div className="space-y-0.5 max-h-40 overflow-y-auto">
                  {(curriculum.path || []).map((p, i) => (
                    <Link
                      key={p.slug}
                      to={`/tutorials/${p.slug}`}
                      className={`block text-[11px] py-1 px-2 rounded truncate ${
                        p.slug === tutorial.slug
                          ? 'bg-accent-cyan/10 text-accent-cyan font-medium border border-accent-cyan/20'
                          : 'text-surface-500 hover:text-surface-300'
                      }`}
                    >
                      {p.level_track ? `${String(i + 1).padStart(2, '0')}. [${p.level_track}] ` : `${String(i + 1).padStart(2, '0')}. `}{p.title}
                    </Link>
                  ))}
                </div>
              </FixitPanel>

              <FixitPanel padding="p-4">
                <div className="flex items-center gap-2 mb-3">
                  <ListTree size={14} className="text-accent-cyan" />
                  <p className="tutorial-sidebar-title">Topics & subtopics</p>
                </div>
                <SectionNav sections={sections} activeOrder={activeSection} />
              </FixitPanel>

              {(linkedScenario || (tutorial.related_scenarios || []).length > 0) && (
                <FixitPanel padding="p-4" className="border-accent-cyan/10">
                  <div className="flex items-center gap-2 mb-3">
                    <FlaskConical size={14} className="text-accent-cyan" />
                    <p className="tutorial-sidebar-title">Practice labs</p>
                  </div>
                  <div className="space-y-2">
                    {linkedScenario && (
                      <Link
                        to={`/scenarios/${linkedScenario.slug}`}
                        className="block text-[11px] py-2 px-2 rounded border border-accent-cyan/20 bg-accent-cyan/5 text-accent-cyan hover:bg-accent-cyan/10"
                      >
                        <span className="font-medium">{linkedScenario.title || linkedScenario.slug}</span>
                        <span className="block text-[10px] text-surface-500 mt-0.5">Primary lab for this lesson</span>
                      </Link>
                    )}
                    {(tutorial.related_scenarios || [])
                      .filter((s) => s.slug !== linkedScenario?.slug && s.slug !== tutorial.scenario_slug)
                      .map((s) => (
                        <Link
                          key={s.slug}
                          to={`/scenarios/${s.slug}`}
                          className="block text-[11px] py-1.5 px-2 rounded text-surface-400 hover:text-surface-200 hover:bg-surface-800/50 truncate"
                        >
                          {s.title || s.slug}
                        </Link>
                      ))}
                  </div>
                </FixitPanel>
              )}
            </aside>

            <article>
              <header className="tutorial-hero mb-8">
                <div className="flex flex-wrap items-center gap-2 mb-3">
                  <span className="tutorial-topic-pill">{tutorial.course_title || tutorial.topic}</span>
                  {tutorial.level_track && (
                    <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border border-surface-700 bg-surface-900/40 capitalize ${LEVEL_CLASS[tutorial.level_track] || 'text-surface-300'}`}>
                      {tutorial.level_track} track
                    </span>
                  )}
                  <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full border capitalize ${DIFFICULTY_CLASS[tutorial.difficulty] || DIFFICULTY_CLASS.beginner}`}>
                    {tutorial.difficulty}
                  </span>
                  {curriculum.total_in_topic > 1 && (
                    <span className="text-[10px] text-surface-500 ml-auto">
                      {curriculum.position}/{curriculum.total_in_topic} in track
                    </span>
                  )}
                </div>
                <h1 className="font-display text-3xl sm:text-[2.25rem] font-bold text-white tracking-tight mb-3 leading-tight">
                  {tutorial.title}
                </h1>
                <p className="text-lg text-surface-300 leading-relaxed max-w-2xl">{tutorial.summary}</p>
                <div className="mt-5 p-4 rounded-xl border border-surface-800/80 bg-surface-900/40">
                  <p className="text-[10px] font-bold uppercase tracking-wider text-accent-cyan mb-2">Course content in this lesson</p>
                  <p className="text-xs text-surface-400 leading-relaxed">
                    Theory → Architecture → Concepts → Use cases → Labs → Simulations → Projects →
                    Troubleshooting → Interview & scenario questions → Assessments → Certification prep →
                    Enterprise examples → Best practices → Security → Performance → Monitoring →
                    Real incidents → Root cause analysis → **Notes and key takeaways**
                  </p>
                </div>
                <div className="mt-5 flex flex-wrap items-center gap-4 text-xs text-surface-500">
                  <span className="flex items-center gap-1"><Clock size={13} /> {tutorial.estimated_minutes} min read</span>
                  <span className="flex items-center gap-1"><Layers size={13} /> {sections.length} sections</span>
                </div>
                <div className="mt-5 flex flex-wrap gap-2">
                  {hasScenario && (
                    <Link to={`/scenarios/${tutorial.scenario_slug || linkedScenario?.slug}`} className="btn-primary text-sm inline-flex items-center gap-1.5">
                      <FlaskConical size={14} /> Start matching lab
                    </Link>
                  )}
                  {tutorial.playground_slug && (
                    <Link
                      to={tutorialPlaygroundHref(tutorial.playground_slug, tutorial.scenario_slug)}
                      className="btn-secondary text-sm inline-flex items-center gap-1.5"
                    >
                      <Terminal size={14} /> Try in playground
                    </Link>
                  )}
                  {readingPct < 100 && (
                    <button type="button" onClick={markTutorialComplete} className="text-sm px-3 py-2 rounded-lg border border-surface-700 text-surface-300 hover:text-white hover:border-surface-500">
                      Mark lesson complete
                    </button>
                  )}
                  {readingPct >= 100 && (
                    <span className="text-xs text-accent-green flex items-center gap-1 px-2 py-2">
                      <GraduationCap size={14} /> Lesson completed
                    </span>
                  )}
                </div>
              </header>

              <div className="space-y-5">
                {sections.map((s, i) => {
                  const theme = sectionTheme(s.heading)
                  const done = completedSections.includes(s.order)
                  return (
                    <section
                      key={i}
                      id={`section-${s.order}`}
                      className={`tutorial-section-card scroll-mt-24 ${theme}`}
                    >
                      <div className="tutorial-section-head">
                        <span className={`tutorial-section-num ${done ? 'text-accent-green' : ''}`}>
                          {done ? '✓' : String(i + 1).padStart(2, '0')}
                        </span>
                        <div>
                          <h2 className="tutorial-section-title">{s.heading}</h2>
                          <span className="tutorial-section-badge">{s.heading}</span>
                        </div>
                      </div>
                      <Body text={s.body} />
                      {s.code && <CodeBlock code={s.code} language={s.code_language} caption={s.code_caption} />}
                      {s.quiz && (
                        <TutorialQuiz
                          quiz={s.quiz}
                          onPassed={() => persistSectionProgress(s.order)}
                        />
                      )}
                    </section>
                  )
                })}
              </div>

              <div className="mt-10 grid sm:grid-cols-2 gap-3">
                {curriculum.prev ? (
                  <Link
                    to={`/tutorials/${curriculum.prev.slug}`}
                    className="group tutorial-track-card p-4 flex items-center gap-3"
                  >
                    <ChevronLeft size={18} className="text-surface-500 group-hover:text-accent-cyan shrink-0" />
                    <div className="min-w-0">
                      <p className="text-[10px] uppercase tracking-wider text-surface-500">Previous</p>
                      <p className="text-sm font-medium text-white truncate group-hover:text-accent-cyan">{curriculum.prev.title}</p>
                    </div>
                  </Link>
                ) : <div />}
                {curriculum.next ? (
                  <Link
                    to={`/tutorials/${curriculum.next.slug}`}
                    className="group tutorial-track-card p-4 flex items-center justify-end gap-3 text-right"
                  >
                    <div className="min-w-0">
                      <p className="text-[10px] uppercase tracking-wider text-surface-500">Next lesson</p>
                      <p className="text-sm font-medium text-white truncate group-hover:text-accent-cyan">{curriculum.next.title}</p>
                    </div>
                    <ChevronRight size={18} className="text-surface-500 group-hover:text-accent-cyan shrink-0" />
                  </Link>
                ) : null}
              </div>
            </article>
          </div>
        </div>
      </div>
    </PublicLayout>
  )
}
