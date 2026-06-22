import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  Clock, Layers, ChevronLeft, Terminal, FlaskConical, ArrowRight, Copy, Check, BookOpen,
} from 'lucide-react'
import PublicLayout from '../../components/layout/PublicLayout'
import { FixitPanel } from '../../components/design'
import { usePageTitle } from '../../hooks/usePageTitle'
import { tutorialApi } from '../../api/tutorials'

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
    <figure className="my-4">
      <div className="relative rounded-lg border border-surface-800 bg-surface-950 overflow-hidden">
        <div className="flex items-center justify-between px-3 py-1.5 border-b border-surface-800 bg-surface-900/60">
          <span className="text-[10px] font-mono uppercase tracking-wider text-surface-500">{language || 'code'}</span>
          <button
            onClick={copy}
            className="flex items-center gap-1 text-[11px] text-surface-400 hover:text-accent-cyan transition-colors"
          >
            {copied ? <Check size={12} className="text-accent-green" /> : <Copy size={12} />}
            {copied ? 'Copied' : 'Copy'}
          </button>
        </div>
        <pre className="p-4 overflow-x-auto text-[13px] leading-relaxed font-mono text-surface-200">
          <code>{code}</code>
        </pre>
      </div>
      {caption && <figcaption className="mt-1.5 text-xs text-surface-500 italic">{caption}</figcaption>}
    </figure>
  )
}

function Body({ text }) {
  if (!text) return null
  // Render blank-line-separated paragraphs; keep it simple and safe (no HTML).
  return (
    <>
      {text.split('\n\n').map((para, i) => (
        <p key={i} className="text-[15px] text-surface-300 leading-relaxed mb-3 whitespace-pre-line">{para}</p>
      ))}
    </>
  )
}

export default function TutorialDetail() {
  const { slug } = useParams()
  const [tutorial, setTutorial] = useState(null)
  const [loading, setLoading] = useState(true)
  const [notFound, setNotFound] = useState(false)

  usePageTitle(
    tutorial?.meta_title || 'Tutorial',
    tutorial?.meta_description || '',
  )

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

  // Keep the <meta name="keywords"> tag in sync for SEO.
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

  if (loading) {
    return (
      <PublicLayout>
        <div className="max-w-3xl mx-auto px-4 py-16">
          <div className="h-8 w-2/3 bg-surface-800 rounded animate-pulse mb-4" />
          <div className="h-4 w-full bg-surface-900 rounded animate-pulse mb-2" />
          <div className="h-4 w-5/6 bg-surface-900 rounded animate-pulse" />
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
          <p className="text-surface-400 mb-6">This tutorial may have moved or been unpublished.</p>
          <Link to="/tutorials" className="btn-primary text-sm">Back to all tutorials</Link>
        </div>
      </PublicLayout>
    )
  }

  const sections = tutorial.sections || []
  const hasPlayground = Boolean(tutorial.playground_slug)
  const hasScenario = Boolean(tutorial.scenario_slug)

  return (
    <PublicLayout>
      <div className="relative overflow-hidden">
        <div className="absolute inset-0 aurora-bg opacity-30 pointer-events-none" aria-hidden="true" />
        <article className="relative max-w-3xl mx-auto px-4 sm:px-6 py-12">
          <Link to="/tutorials" className="inline-flex items-center gap-1.5 text-sm text-surface-400 hover:text-accent-cyan mb-6 transition-colors">
            <ChevronLeft size={15} /> All tutorials
          </Link>

          {/* Header */}
          <header className="mb-8">
            <div className="flex items-center gap-2 mb-3">
              <span className="text-[11px] font-medium uppercase tracking-wider text-accent-cyan">{tutorial.topic}</span>
              <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full border capitalize ${DIFFICULTY_CLASS[tutorial.difficulty] || DIFFICULTY_CLASS.beginner}`}>
                {tutorial.difficulty}
              </span>
            </div>
            <h1 className="font-display text-3xl sm:text-4xl font-bold text-white tracking-tight mb-3">{tutorial.title}</h1>
            <p className="text-lg text-surface-300 leading-relaxed">{tutorial.summary}</p>
            <div className="mt-4 flex items-center gap-4 text-xs text-surface-500">
              <span className="flex items-center gap-1"><Clock size={13} /> {tutorial.estimated_minutes} min read</span>
              <span className="flex items-center gap-1"><Layers size={13} /> {sections.length} sections</span>
            </div>
          </header>

          {/* Top CTA */}
          {(hasPlayground || hasScenario) && (
            <FixitPanel className="mb-8 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3" padding="p-4">
              <p className="text-sm text-surface-300">
                Follow along hands-on while you read.
              </p>
              <div className="flex gap-2 shrink-0">
                {hasPlayground && (
                  <Link to={`/playgrounds/${tutorial.playground_slug}`} className="btn-primary text-sm inline-flex items-center gap-1.5">
                    <Terminal size={14} /> Try it now
                  </Link>
                )}
                {hasScenario && (
                  <Link to={`/scenarios/${tutorial.scenario_slug}`} className="btn-secondary text-sm inline-flex items-center gap-1.5">
                    <FlaskConical size={14} /> Start a lab
                  </Link>
                )}
              </div>
            </FixitPanel>
          )}

          {/* Sections */}
          <div className="space-y-8">
            {sections.map((s, i) => (
              <section key={i} id={`section-${s.order}`} className="scroll-mt-24">
                <h2 className="font-display text-xl font-semibold text-white mb-3 flex items-baseline gap-2">
                  <span className="text-accent-cyan/60 text-base font-mono">{String(i + 1).padStart(2, '0')}</span>
                  {s.heading}
                </h2>
                <Body text={s.body} />
                {s.code && <CodeBlock code={s.code} language={s.code_language} caption={s.code_caption} />}
              </section>
            ))}
          </div>

          {/* Bottom CTA */}
          {(hasPlayground || hasScenario) && (
            <FixitPanel hero className="mt-12 text-center" padding="p-6">
              <h2 className="font-display text-xl font-bold text-white mb-2">Ready to practise?</h2>
              <p className="text-sm text-surface-300 mb-4 max-w-md mx-auto">
                You've read the concepts — now make them stick by running the commands yourself.
              </p>
              <div className="flex flex-wrap gap-2 justify-center">
                {hasPlayground && (
                  <Link to={`/playgrounds/${tutorial.playground_slug}`} className="btn-primary text-sm inline-flex items-center gap-1.5">
                    <Terminal size={14} /> Open the playground
                  </Link>
                )}
                {hasScenario && (
                  <Link to={`/scenarios/${tutorial.scenario_slug}`} className="btn-secondary text-sm inline-flex items-center gap-1.5">
                    <FlaskConical size={14} /> Start a guided lab
                  </Link>
                )}
              </div>
            </FixitPanel>
          )}

          {/* Related */}
          {tutorial.related?.length > 0 && (
            <div className="mt-12">
              <h2 className="font-display text-lg font-semibold text-white mb-4">More {tutorial.topic} tutorials</h2>
              <div className="grid sm:grid-cols-2 gap-3">
                {tutorial.related.map((r) => (
                  <Link key={r.slug} to={`/tutorials/${r.slug}`} className="group fx-panel p-4 flex items-center justify-between gap-3 hover:border-accent-cyan/40 transition-colors">
                    <div className="min-w-0">
                      <p className="font-medium text-surface-100 truncate group-hover:text-accent-cyan transition-colors">{r.title}</p>
                      <p className="text-xs text-surface-500 truncate">{r.summary}</p>
                    </div>
                    <ArrowRight size={15} className="text-surface-600 group-hover:text-accent-cyan shrink-0 transition-colors" />
                  </Link>
                ))}
              </div>
            </div>
          )}
        </article>
      </div>
    </PublicLayout>
  )
}
