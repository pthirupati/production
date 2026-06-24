import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import {
  Clock, Layers, ChevronLeft, ChevronRight, Terminal, FlaskConical,
  Copy, Check, BookOpen, ListTree, GraduationCap,
} from 'lucide-react'
import PublicLayout from '../../components/layout/PublicLayout'
import { FixitPanel } from '../../components/design'
import { usePageTitle } from '../../hooks/usePageTitle'
import { tutorialApi } from '../../api/tutorials'
import { tutorialPlaygroundHref } from '../../utils/playgroundLinks'
import { useAuthStore } from '../../store/authStore'

const DIFFICULTY_CLASS = {
  beginner: 'text-accent-green bg-accent-green/10 border-accent-green/20',
  intermediate: 'text-accent-amber bg-accent-amber/10 border-accent-amber/20',
  advanced: 'text-accent-red bg-accent-red/10 border-accent-red/20',
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
    <figure className="my-5">
      <div className="relative rounded-xl border border-accent-cyan/15 bg-surface-950 overflow-hidden shadow-lg shadow-black/20">
        <div className="flex items-center justify-between px-4 py-2 border-b border-surface-800 bg-gradient-to-r from-surface-900/90 to-surface-900/40">
          <span className="text-[10px] font-mono uppercase tracking-wider text-accent-cyan/80">{language || 'code'}</span>
          <button
            onClick={copy}
            className="flex items-center gap-1 text-[11px] text-surface-400 hover:text-accent-cyan transition-colors"
          >
            {copied ? <Check size={12} className="text-accent-green" /> : <Copy size={12} />}
            {copied ? 'Copied' : 'Copy'}
          </button>
        </div>
        <pre className="p-4 overflow-x-auto text-[13px] leading-relaxed font-mono text-surface-100">
          <code>{code}</code>
        </pre>
      </div>
      {caption && <figcaption className="mt-2 text-xs text-surface-500 italic pl-1">{caption}</figcaption>}
    </figure>
  )
}

function Body({ text }) {
  if (!text) return null
  return (
    <div className="tutorial-prose space-y-4">
      {text.split('\n\n').map((para, i) => (
        <p key={i} className="text-[15px] text-surface-200 leading-[1.75] whitespace-pre-line">{para}</p>
      ))}
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
            className={`block px-2 py-1.5 rounded-lg text-xs transition-colors truncate ${
              active
                ? 'bg-accent-cyan/10 text-accent-cyan border border-accent-cyan/20'
                : 'text-surface-400 hover:text-surface-200 hover:bg-surface-800/50'
            }`}
          >
            <span className="font-mono text-[10px] text-surface-600 mr-1.5">{String(i + 1).padStart(2, '0')}</span>
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
      })
      .catch(() => { if (!cancelled) setNotFound(true) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [slug])

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

  // Highlight active section in sidebar while scrolling
  useEffect(() => {
    if (!tutorial?.sections?.length) return
    const obs = new IntersectionObserver(
      (entries) => {
        const visible = entries.filter((e) => e.isIntersecting).sort((a, b) => b.intersectionRatio - a.intersectionRatio)
        if (visible[0]?.target?.id) {
          const order = Number(visible[0].target.id.replace('section-', ''))
          if (!Number.isNaN(order)) setActiveSection(order)
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
        <div className="max-w-6xl mx-auto px-4 py-16">
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
        <div className="max-w-2xl mx-auto px-4 py-24 text-center">
          <BookOpen size={36} className="mx-auto mb-4 text-surface-600" />
          <h1 className="font-display text-2xl font-bold text-white mb-2">Tutorial not found</h1>
          <Link to="/tutorials" className="btn-primary text-sm">Back to all tutorials</Link>
        </div>
      </PublicLayout>
    )
  }

  const sections = tutorial.sections || []
  const curriculum = tutorial.curriculum || {}
  const hasPlayground = Boolean(tutorial.playground_slug)
  const hasScenario = Boolean(tutorial.scenario_slug)
  const playgroundHref = hasPlayground
    ? tutorialPlaygroundHref(tutorial.playground_slug, tutorial.scenario_slug)
    : null
  const progressPct = curriculum.total_in_topic
    ? Math.round((curriculum.position / curriculum.total_in_topic) * 100)
    : 0

  const openPlayground = (e) => {
    if (!playgroundHref) return
    if (!isAuthenticated && playgroundHref.startsWith('/technologies')) {
      e.preventDefault()
      navigate('/login', { state: { from: playgroundHref } })
    }
  }

  return (
    <PublicLayout>
      <div className="relative overflow-hidden min-h-screen">
        <div className="absolute inset-0 aurora-bg opacity-25 pointer-events-none" aria-hidden="true" />
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[300px] bg-accent-cyan/[0.04] blur-[100px] pointer-events-none" />

        <div className="relative max-w-6xl mx-auto px-4 sm:px-6 py-10">
          {/* Breadcrumb */}
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
            {/* Sidebar — curriculum + section TOC */}
            <aside className="hidden lg:block sticky top-24 space-y-6">
              <FixitPanel padding="p-4" className="border-accent-cyan/10">
                <div className="flex items-center gap-2 mb-3">
                  <GraduationCap size={16} className="text-accent-cyan" />
                  <p className="text-xs font-semibold text-white">{curriculum.topic} path</p>
                </div>
                <p className="text-[10px] text-surface-500 mb-2">
                  Lesson {curriculum.position} of {curriculum.total_in_topic}
                </p>
                <div className="h-1.5 bg-surface-800 rounded-full overflow-hidden mb-3">
                  <div className="h-full bg-accent-cyan rounded-full transition-all" style={{ width: `${progressPct}%` }} />
                </div>
                <div className="space-y-0.5 max-h-40 overflow-y-auto">
                  {(curriculum.path || []).map((p, i) => (
                    <Link
                      key={p.slug}
                      to={`/tutorials/${p.slug}`}
                      className={`block text-[11px] py-1 px-2 rounded truncate ${
                        p.slug === tutorial.slug
                          ? 'bg-accent-cyan/10 text-accent-cyan font-medium'
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
                  <ListTree size={14} className="text-surface-400" />
                  <p className="text-xs font-semibold text-surface-300">Topics & subtopics</p>
                </div>
                <SectionNav sections={sections} activeOrder={activeSection} />
              </FixitPanel>
            </aside>

            {/* Main content */}
            <article>
              <header className="mb-8 fx-panel p-6 sm:p-8 border-accent-cyan/10 bg-gradient-to-br from-surface-900/80 via-surface-900/40 to-accent-cyan/[0.03]">
                <div className="flex flex-wrap items-center gap-2 mb-3">
                  <span className="text-[11px] font-bold uppercase tracking-wider text-accent-cyan">{tutorial.course_title || tutorial.topic}</span>
                  {tutorial.level_track && (
                    <span className="text-[10px] font-medium px-2 py-0.5 rounded-full border border-accent-purple/30 text-accent-purple capitalize">{tutorial.level_track}</span>
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
                <div className="mt-5 flex flex-wrap items-center gap-4 text-xs text-surface-500">
                  <span className="flex items-center gap-1"><Clock size={13} /> {tutorial.estimated_minutes} min</span>
                  <span className="flex items-center gap-1"><Layers size={13} /> {sections.length} topics</span>
                </div>
                {(hasPlayground || hasScenario) && (
                  <div className="mt-5 flex flex-wrap gap-2">
                    {hasPlayground && (
                      <Link to={playgroundHref} onClick={openPlayground} className="btn-primary text-sm inline-flex items-center gap-1.5">
                        <Terminal size={14} /> Try hands-on
                      </Link>
                    )}
                    {hasScenario && (
                      <Link to={`/scenarios/${tutorial.scenario_slug}`} className="btn-secondary text-sm inline-flex items-center gap-1.5">
                        <FlaskConical size={14} /> Start lab
                      </Link>
                    )}
                  </div>
                )}
              </header>

              <div className="space-y-6">
                {sections.map((s, i) => (
                  <section
                    key={i}
                    id={`section-${s.order}`}
                    className="scroll-mt-24 fx-panel p-6 sm:p-7 border-surface-800/80 hover:border-accent-cyan/15 transition-colors"
                  >
                    <h2 className="font-display text-xl font-semibold text-white mb-4 flex items-start gap-3">
                      <span className="shrink-0 w-8 h-8 rounded-lg bg-accent-cyan/10 border border-accent-cyan/20 flex items-center justify-center text-accent-cyan text-sm font-mono">
                        {String(i + 1).padStart(2, '0')}
                      </span>
                      <span className="pt-0.5">{s.heading}</span>
                    </h2>
                    <Body text={s.body} />
                    {s.code && <CodeBlock code={s.code} language={s.code_language} caption={s.code_caption} />}
                  </section>
                ))}
              </div>

              {/* Prev / Next */}
              <div className="mt-10 grid sm:grid-cols-2 gap-3">
                {curriculum.prev ? (
                  <Link
                    to={`/tutorials/${curriculum.prev.slug}`}
                    className="group fx-panel p-4 flex items-center gap-3 hover:border-accent-cyan/30 transition-colors"
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
                    className="group fx-panel p-4 flex items-center justify-end gap-3 hover:border-accent-cyan/30 transition-colors text-right"
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
