import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { BookOpen, Clock, ArrowRight, Layers, Terminal, Search, GraduationCap, ChevronDown, ChevronRight } from 'lucide-react'
import PublicLayout from '../../components/layout/PublicLayout'
import MarketingPageShell from '../../components/MarketingPageShell'
import { FixitPanel } from '../../components/design'
import { usePageTitle } from '../../hooks/usePageTitle'
import { tutorialApi } from '../../api/tutorials'

const DIFFICULTY_CLASS = {
  beginner: 'text-accent-green bg-accent-green/10 border-accent-green/20',
  intermediate: 'text-accent-amber bg-accent-amber/10 border-accent-amber/20',
  advanced: 'text-accent-red bg-accent-red/10 border-accent-red/20',
  expert: 'text-pink-400 bg-pink-500/10 border-pink-500/20',
  enterprise: 'text-accent-purple bg-accent-purple/10 border-accent-purple/20',
}

function TutorialCard({ t }) {
  return (
    <Link
      to={`/tutorials/${t.slug}`}
      className="group tutorial-track-card p-5 flex flex-col hover:border-accent-cyan/40 transition-all hover:shadow-lg hover:shadow-accent-cyan/5"
    >
      <div className="flex items-center justify-between gap-2 mb-3">
        <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border capitalize ${DIFFICULTY_CLASS[t.difficulty] || DIFFICULTY_CLASS.beginner}`}>
          {t.difficulty}
        </span>
        {t.level_track && (
          <span className={`text-[10px] font-medium capitalize tutorial-level-${t.level_track}`}>{t.level_track}</span>
        )}
        <span className="text-[10px] text-surface-500 ml-auto">{t.section_count} sections</span>
      </div>
      <p className="text-[10px] font-bold uppercase tracking-wider text-accent-cyan mb-1">{t.topic}</p>
      <h3 className="font-display font-semibold text-white text-base leading-snug mb-2 group-hover:text-accent-cyan transition-colors">
        {t.title}
      </h3>
      <p className="text-sm text-surface-400 leading-relaxed flex-1 line-clamp-2">{t.summary}</p>
      <div className="mt-4 pt-3 border-t border-surface-800 flex items-center justify-between text-xs text-surface-500">
        <span className="flex items-center gap-1"><Clock size={12} /> {t.estimated_minutes} min</span>
        <span className="flex items-center gap-1 text-accent-cyan opacity-0 group-hover:opacity-100 transition-opacity">
          Start <ArrowRight size={12} />
        </span>
      </div>
    </Link>
  )
}

function CourseTrack({ course, defaultOpen }) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <section className="tutorial-track-card overflow-hidden tutorial-course-header">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center gap-4 p-5 text-left hover:bg-surface-800/30 transition-colors"
      >
        <div className="w-11 h-11 rounded-xl bg-gradient-to-br from-accent-purple/25 to-accent-cyan/10 border border-accent-purple/25 flex items-center justify-center shrink-0">
          <Layers size={20} className="text-accent-purple" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-[10px] font-bold uppercase tracking-wider text-accent-purple mb-0.5">{course.topic}</p>
          <h2 className="font-display font-bold text-white text-lg">{course.course_title}</h2>
          <p className="text-xs text-surface-400 mt-0.5">
            {course.module_count} modules · {course.total_sections} sections · beginner → enterprise · full textbook + notes per module
          </p>
        </div>
        {open ? <ChevronDown size={18} className="text-surface-500 shrink-0" /> : <ChevronRight size={18} className="text-surface-500 shrink-0" />}
      </button>
      {open && (
        <div className="px-5 pb-5 pt-0 space-y-2 border-t border-surface-800/60">
          {course.modules.map((t, i) => (
            <Link
              key={t.slug}
              to={`/tutorials/${t.slug}`}
              className="group flex items-center gap-3 p-3 rounded-lg border border-surface-800/80 hover:border-accent-purple/30 hover:bg-surface-900/50 transition-colors"
            >
              <span className="shrink-0 w-8 h-8 rounded-lg bg-surface-800 border border-surface-700 flex items-center justify-center text-xs font-mono text-surface-400 group-hover:text-accent-purple">
                {String(i + 1).padStart(2, '0')}
              </span>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-white truncate group-hover:text-accent-cyan">{t.title}</p>
                <p className="text-[11px] text-surface-500 truncate">{t.summary}</p>
              </div>
              {t.level_track && (
                <span className={`hidden sm:inline text-[10px] px-2 py-0.5 rounded-full border border-surface-700 capitalize tutorial-level-${t.level_track}`}>{t.level_track}</span>
              )}
              <ArrowRight size={14} className="text-surface-600 group-hover:text-accent-cyan shrink-0" />
            </Link>
          ))}
        </div>
      )}
    </section>
  )
}

function TechnologyTrack({ track, defaultOpen }) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <section className="tutorial-track-card overflow-hidden tutorial-tech-header">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center gap-4 p-5 text-left hover:bg-surface-800/30 transition-colors"
      >
        <div className="w-11 h-11 rounded-xl bg-gradient-to-br from-accent-cyan/20 to-accent-purple/10 border border-accent-cyan/20 flex items-center justify-center shrink-0">
          <GraduationCap size={20} className="text-accent-cyan" />
        </div>
        <div className="flex-1 min-w-0">
          <h2 className="font-display font-bold text-white text-lg">{track.topic}</h2>
          <p className="text-xs text-surface-400 mt-0.5">
            {track.tutorial_count} tutorials · {track.total_sections} topics · zero to hero learning path
          </p>
        </div>
        {open ? <ChevronDown size={18} className="text-surface-500 shrink-0" /> : <ChevronRight size={18} className="text-surface-500 shrink-0" />}
      </button>
      {open && (
        <div className="px-5 pb-5 pt-0 grid sm:grid-cols-2 lg:grid-cols-3 gap-4 border-t border-surface-800/60">
          {track.tutorials.map((t) => <TutorialCard key={t.slug} t={t} />)}
        </div>
      )}
    </section>
  )
}

export default function Tutorials() {
  const [searchParams] = useSearchParams()
  const [curriculum, setCurriculum] = useState([])
  const [courses, setCourses] = useState([])
  const [topics, setTopics] = useState([])
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(true)
  const topicParam = searchParams.get('topic') || ''

  usePageTitle(
    'Free Tech Tutorials',
    'Original, hands-on tutorials on Linux, Git, Docker, Kubernetes, Python, and more — organized by technology with step-by-step topics from zero to hero.',
  )

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    Promise.all([
      tutorialApi.curriculum().catch(() => ({ curriculum: [] })),
      tutorialApi.list().catch(() => ({ topics: [] })),
    ])
      .then(([cur, list]) => {
        if (cancelled) return
        setCurriculum(cur?.curriculum || [])
        setCourses(cur?.courses || [])
        setTopics(list?.topics || [])
      })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [])

  const filteredCourses = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q && !topicParam) return courses
    return courses
      .map((course) => ({
        ...course,
        modules: course.modules.filter((t) => {
          if (topicParam && t.topic !== topicParam) return false
          if (q && !(`${t.title} ${t.summary} ${course.course_title} ${t.topic}`.toLowerCase().includes(q))) return false
          return true
        }),
      }))
      .filter((course) => course.modules.length > 0)
      .map((course) => ({
        ...course,
        module_count: course.modules.length,
        total_sections: course.modules.reduce((n, t) => n + (t.section_count || 0), 0),
      }))
  }, [courses, query, topicParam])

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q && !topicParam) return curriculum
    return curriculum
      .map((track) => ({
        ...track,
        tutorials: track.tutorials.filter((t) => {
          if (topicParam && t.topic !== topicParam) return false
          if (q && !(`${t.title} ${t.summary} ${t.topic}`.toLowerCase().includes(q))) return false
          return true
        }),
      }))
      .filter((track) => track.tutorials.length > 0)
      .map((track) => ({
        ...track,
        tutorial_count: track.tutorials.length,
        total_sections: track.tutorials.reduce((n, t) => n + (t.section_count || 0), 0),
      }))
  }, [curriculum, query, topicParam])

  return (
    <PublicLayout>
      <div className="tutorial-page">
      <MarketingPageShell
        eyebrow="Learn by doing"
        title="Technology Tutorials"
        subtitle="Complete learning paths organized by technology — each tutorial breaks down into topics and subtopics with hands-on practice. Start at lesson 1 and follow the path to mastery."
      >
        <div className="mb-8 flex flex-col sm:flex-row gap-3 items-stretch sm:items-center justify-between">
          <div className="relative w-full sm:max-w-xs">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-surface-500" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search tutorials…"
              className="w-full pl-9 pr-3 py-2 rounded-lg bg-surface-900 border border-surface-700 text-sm text-surface-100 placeholder:text-surface-500 focus:border-accent-cyan focus:outline-none focus:ring-2 focus:ring-accent-cyan/20"
            />
          </div>
          <div className="flex flex-wrap gap-1.5">
            <Link
              to="/tutorials"
              className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-colors ${!topicParam ? 'border-accent-cyan/50 text-accent-cyan bg-accent-cyan/10' : 'border-surface-700 text-surface-400 hover:text-surface-200'}`}
            >
              All technologies
            </Link>
            {topics.map((topic) => (
              <Link
                key={topic}
                to={`/tutorials?topic=${encodeURIComponent(topic)}`}
                className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-colors ${topicParam === topic ? 'border-accent-cyan/50 text-accent-cyan bg-accent-cyan/10' : 'border-surface-700 text-surface-400 hover:text-surface-200'}`}
              >
                {topic}
              </Link>
            ))}
          </div>
        </div>

        <FixitPanel className="mb-8 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4" padding="p-5">
          <div className="flex items-start gap-3">
            <Terminal size={20} className="text-accent-purple mt-0.5 shrink-0" />
            <div>
              <h2 className="font-display font-semibold text-white">Preparing for a certification?</h2>
              <p className="text-sm text-surface-400">Follow an objective-mapped track with hands-on labs and a timed practice exam.</p>
            </div>
          </div>
          <Link to="/certifications" className="btn-secondary text-sm shrink-0">Browse Certifications</Link>
        </FixitPanel>

        {loading ? (
          <div className="space-y-4">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="fx-panel h-32 animate-pulse bg-surface-900/40" />
            ))}
          </div>
        ) : filtered.length === 0 && filteredCourses.length === 0 ? (
          <div className="text-center py-16 text-surface-500">
            <BookOpen size={32} className="mx-auto mb-3 opacity-50" />
            <p>No tutorials match your search yet.</p>
          </div>
        ) : (
          <div className="space-y-5">
            {filteredCourses.length > 0 ? (
              <div className="space-y-4">
                <h2 className="text-sm font-semibold text-surface-300 flex items-center gap-2">
                  <Layers size={16} className="text-accent-purple" /> Course curriculum
                </h2>
                <p className="text-xs text-surface-500 -mt-2">
                  Expand a course to see every module in order — like TutorialsPoint or JavaPoint. Each module has 20 sections with diagrams, shell commands, code, and quizzes.
                </p>
                {filteredCourses.map((course, i) => (
                  <CourseTrack key={course.course_slug} course={course} defaultOpen={i === 0 && !topicParam} />
                ))}
              </div>
            ) : filtered.length > 0 ? (
              filtered.map((track, i) => (
                <TechnologyTrack key={track.topic} track={track} defaultOpen={!topicParam || topicParam === track.topic || i === 0} />
              ))
            ) : null}
          </div>
        )}
      </MarketingPageShell>
      </div>
    </PublicLayout>
  )
}
