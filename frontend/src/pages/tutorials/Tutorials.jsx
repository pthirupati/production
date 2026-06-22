import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { BookOpen, Clock, ArrowRight, Layers, Terminal, Search } from 'lucide-react'
import PublicLayout from '../../components/layout/PublicLayout'
import MarketingPageShell from '../../components/MarketingPageShell'
import { FixitPanel } from '../../components/design'
import { usePageTitle } from '../../hooks/usePageTitle'
import { tutorialApi } from '../../api/tutorials'

const DIFFICULTY_CLASS = {
  beginner: 'text-accent-green bg-accent-green/10 border-accent-green/20',
  intermediate: 'text-accent-amber bg-accent-amber/10 border-accent-amber/20',
  advanced: 'text-accent-red bg-accent-red/10 border-accent-red/20',
}

function TutorialCard({ t }) {
  return (
    <Link
      to={`/tutorials/${t.slug}`}
      className="group fx-panel p-5 flex flex-col hover:border-accent-cyan/40 transition-colors"
    >
      <div className="flex items-center justify-between gap-2 mb-3">
        <span className="text-[11px] font-medium uppercase tracking-wider text-accent-cyan">{t.topic}</span>
        <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full border capitalize ${DIFFICULTY_CLASS[t.difficulty] || DIFFICULTY_CLASS.beginner}`}>
          {t.difficulty}
        </span>
      </div>
      <h3 className="font-display font-semibold text-white text-lg leading-snug mb-2 group-hover:text-accent-cyan transition-colors">
        {t.title}
      </h3>
      <p className="text-sm text-surface-400 leading-relaxed flex-1">{t.summary}</p>
      <div className="mt-4 pt-3 border-t border-surface-800 flex items-center justify-between text-xs text-surface-500">
        <span className="flex items-center gap-3">
          <span className="flex items-center gap-1"><Clock size={12} /> {t.estimated_minutes} min</span>
          <span className="flex items-center gap-1"><Layers size={12} /> {t.section_count} steps</span>
        </span>
        <span className="flex items-center gap-1 text-accent-cyan opacity-0 group-hover:opacity-100 transition-opacity">
          Read <ArrowRight size={12} />
        </span>
      </div>
    </Link>
  )
}

export default function Tutorials() {
  const [tutorials, setTutorials] = useState([])
  const [topics, setTopics] = useState([])
  const [activeTopic, setActiveTopic] = useState('')
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(true)

  usePageTitle(
    'Free Tech Tutorials',
    'Original, hands-on tutorials on Linux, Git, Docker, Kubernetes, Python, Bash, SQL, and Ansible — each with a free playground to try it.',
  )

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    tutorialApi.list()
      .then((data) => {
        if (cancelled) return
        setTutorials(data?.tutorials || [])
        setTopics(data?.topics || [])
      })
      .catch(() => {})
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [])

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    return tutorials.filter((t) => {
      if (activeTopic && t.topic !== activeTopic) return false
      if (q && !(`${t.title} ${t.summary} ${t.topic}`.toLowerCase().includes(q))) return false
      return true
    })
  }, [tutorials, activeTopic, query])

  return (
    <PublicLayout>
      <MarketingPageShell
        eyebrow="Learn by doing"
        title="Free Tutorials"
        subtitle="Concise, original guides on the tools that run modern infrastructure. Every tutorial ends with a free, no-signup playground or lab so you can try it immediately."
      >
        {/* Controls */}
        <div className="mb-8 flex flex-col sm:flex-row gap-3 items-stretch sm:items-center justify-between">
          <div className="relative w-full sm:max-w-xs">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-surface-500" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search tutorials…"
              className="w-full pl-9 pr-3 py-2 rounded-lg bg-surface-900 border border-surface-700 text-sm text-surface-100 placeholder:text-surface-500 focus:border-accent-cyan focus:outline-none"
            />
          </div>
          <div className="flex flex-wrap gap-1.5">
            <button
              onClick={() => setActiveTopic('')}
              className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-colors ${activeTopic === '' ? 'border-accent-cyan/50 text-accent-cyan bg-accent-cyan/10' : 'border-surface-700 text-surface-400 hover:text-surface-200'}`}
            >
              All
            </button>
            {topics.map((topic) => (
              <button
                key={topic}
                onClick={() => setActiveTopic(topic)}
                className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-colors ${activeTopic === topic ? 'border-accent-cyan/50 text-accent-cyan bg-accent-cyan/10' : 'border-surface-700 text-surface-400 hover:text-surface-200'}`}
              >
                {topic}
              </button>
            ))}
          </div>
        </div>

        {/* Playgrounds cross-link */}
        <FixitPanel className="mb-8 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4" padding="p-5">
          <div className="flex items-start gap-3">
            <Terminal size={20} className="text-accent-purple mt-0.5 shrink-0" />
            <div>
              <h2 className="font-display font-semibold text-white">Prefer to just start typing?</h2>
              <p className="text-sm text-surface-400">Open a Playground and run real commands in your browser — no account needed.</p>
            </div>
          </div>
          <Link to="/playgrounds" className="btn-secondary text-sm shrink-0">Browse Playgrounds</Link>
        </FixitPanel>

        {/* Grid */}
        {loading ? (
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="fx-panel p-5 h-44 animate-pulse bg-surface-900/40" />
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <div className="text-center py-16 text-surface-500">
            <BookOpen size={32} className="mx-auto mb-3 opacity-50" />
            <p>No tutorials match your search yet.</p>
          </div>
        ) : (
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
            {filtered.map((t) => <TutorialCard key={t.slug} t={t} />)}
          </div>
        )}
      </MarketingPageShell>
    </PublicLayout>
  )
}
