import { useState, useEffect } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { scenarioApi } from '../api/scenarios'
import { useAuthStore } from '../store/authStore'
import { useDataStore } from '../store/dataStore'
import {
  Search, CheckCircle2, Clock, Wrench, Play, Skull,
  BookmarkPlus, Bookmark, Filter, X, Hash, Trophy, Lock,
  ChevronRight, Zap, Target, AlertTriangle, Flame,
} from 'lucide-react'
import toast from 'react-hot-toast'
import Pagination from '../components/Pagination'
import StickyPageToolbar from '../components/StickyPageToolbar'
import { useScrollHideToolbar } from '../hooks/useScrollHideToolbar'
import { PageHeader } from '../components/design'
import { ScenarioStatsChip } from '../components/engagement'
import { usePageTitle } from '../hooks/usePageTitle'

const typeConfig = {
  fix:  { icon: Wrench,  label: 'Fix',  color: 'bg-accent-cyan/10 text-accent-cyan border-accent-cyan/20',    border: 'border-l-accent-cyan',   glow: 'hover:shadow-[0_0_20px_rgba(6,182,212,0.06)]' },
  do:   { icon: Play,    label: 'Do',   color: 'bg-accent-green/10 text-accent-green border-accent-green/20',   border: 'border-l-accent-green',  glow: 'hover:shadow-[0_0_20px_rgba(34,197,94,0.06)]' },
  hack: { icon: Skull,   label: 'Hack', color: 'bg-accent-red/10 text-accent-red border-accent-red/20',         border: 'border-l-accent-red',    glow: 'hover:shadow-[0_0_20px_rgba(239,68,68,0.06)]' },
}

// 'expert' is the fourth tier above hard. It has no badge-* utility of its own —
// index.css only defines easy/medium/hard — so it composes the same badge shape
// inline from purple accents rather than rendering an unstyled chip.
const EXPERT_BADGE = 'badge bg-accent-purple/10 text-accent-purple border border-accent-purple/20'

const difficultyConfig = {
  easy:   { label: 'Easy',   badge: 'badge-easy',   dot: 'bg-accent-green', icon: Zap,           textColor: 'text-accent-green' },
  medium: { label: 'Medium', badge: 'badge-medium',  dot: 'bg-accent-amber', icon: Target,        textColor: 'text-accent-amber' },
  hard:   { label: 'Hard',   badge: 'badge-hard',    dot: 'bg-accent-red',   icon: AlertTriangle, textColor: 'text-accent-red'   },
  expert: { label: 'Expert', badge: EXPERT_BADGE,    dot: 'bg-accent-purple', icon: Flame,        textColor: 'text-accent-purple' },
}

// Difficulty tiers, hardest last. Every difficulty-keyed map below derives from
// this so a fifth tier can never again be added to the model and silently vanish
// from the listing (the old `grouped` map dropped unknown difficulties outright).
const DIFFICULTY_ORDER = Object.keys(difficultyConfig)

function DifficultyDots({ difficulty }) {
  // Unknown difficulty keeps the old single grey dot rather than rendering none.
  const count = Math.max(1, DIFFICULTY_ORDER.indexOf(difficulty) + 1)
  const color = difficultyConfig[difficulty]?.dot || 'bg-surface-600'
  return (
    <span className="flex items-center gap-0.5 shrink-0">
      {DIFFICULTY_ORDER.map((_, i) => (
        <span key={i} className={`w-1.5 h-1.5 rounded-full ${i < count ? color : 'bg-surface-700'}`} />
      ))}
    </span>
  )
}

function TechIcon({ name }) {
  const palettes = [
    'bg-accent-cyan/15 text-accent-cyan',
    'bg-accent-green/15 text-accent-green',
    'bg-accent-purple/15 text-accent-purple',
    'bg-accent-amber/15 text-accent-amber',
  ]
  const idx = name ? name.charCodeAt(0) % palettes.length : 0
  return (
    <span className={`w-6 h-6 rounded text-[10px] font-black flex items-center justify-center shrink-0 ${palettes[idx]}`}>
      {(name || '?').slice(0, 2).toUpperCase()}
    </span>
  )
}

function ScenarioCard({ scenario, index, isAuthenticated, onBookmark }) {
  const typeCfg  = typeConfig[scenario.scenario_type] || typeConfig.fix
  const diffCfg  = difficultyConfig[scenario.difficulty] || difficultyConfig.easy
  const TypeIcon = typeCfg.icon
  const solved    = scenario.user_progress?.completed
  const attempted = !solved && (scenario.user_progress?.attempts ?? 0) > 0
  const bestScore = scenario.user_progress?.best_score

  // Per-scenario stats chip, synthesized from list-serializer fields already on
  // the card (no extra request). Fail rate is derived from raw attempt/completion
  // counts (both real model fields), falling back to the pass-rate complement.
  // Hidden by the chip itself when there's no meaningful data.
  const cardStats = scenario.attempts_count > 0 ? {
    learners: scenario.attempts_count,
    solved: scenario.completions_count,
    avg_solve_seconds: null,
    fail_rate_pct: scenario.completions_count != null
      ? Math.max(0, Math.round((scenario.attempts_count - scenario.completions_count) / scenario.attempts_count * 100))
      : (scenario.completion_rate != null ? Math.max(0, 100 - scenario.completion_rate) : 0),
  } : null

  return (
    <Link
      to={`/scenarios/${scenario.slug}`}
      className={`
        group flex items-center gap-4 px-5 py-4 transition-all duration-200
        border-l-2 ${typeCfg.border} ${typeCfg.glow}
        hover:bg-surface-800/40
      `}
    >
      {/* Row index + completion indicator */}
      <div className="w-8 shrink-0 flex flex-col items-center gap-1.5">
        <span className="text-[10px] text-surface-600 font-mono leading-none tabular-nums">
          {String(index + 1).padStart(2, '0')}
        </span>
        {solved ? (
          <CheckCircle2 size={13} className="text-accent-green" />
        ) : attempted ? (
          <div className="w-3 h-3 rounded-full border-2 border-accent-amber" />
        ) : (
          <div className="w-3 h-3 rounded-full border border-surface-700" />
        )}
      </div>

      {/* Main content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-sm font-semibold text-white group-hover:text-accent-cyan transition-colors truncate">
            {scenario.title}
          </span>
          {scenario.interview_mode && (
            <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-accent-purple/10 text-accent-purple border border-accent-purple/20 shrink-0">
              Interview
            </span>
          )}
        </div>
        {scenario.subtitle && (
          <p className="text-xs text-surface-500 mt-0.5 truncate hidden sm:block leading-relaxed">
            {scenario.subtitle}
          </p>
        )}
        {scenario.learn?.length > 0 && (
          <p className="text-[11px] text-surface-400 mt-1 hidden sm:flex items-start gap-1 leading-relaxed">
            <Target size={11} className="mt-[1px] shrink-0 text-accent-cyan/70" />
            <span className="truncate">
              <span className="text-surface-500">You'll learn: </span>{scenario.learn[0]}
            </span>
          </p>
        )}
        {scenario.tags?.length > 0 && (
          <div className="flex gap-1 mt-1.5 flex-wrap">
            {scenario.tags.slice(0, 3).map(tag => (
              <span key={tag.slug} className="inline-flex items-center gap-0.5 text-[10px] text-surface-500 bg-surface-800 px-1.5 py-0.5 rounded">
                <Hash size={9} />{tag.name}
              </span>
            ))}
          </div>
        )}
        {cardStats && (
          <ScenarioStatsChip stats={cardStats} className="mt-1.5 hidden sm:flex" />
        )}
      </div>

      {/* Right metadata cluster */}
      <div className="flex items-center gap-3 shrink-0">
        {/* Difficulty */}
        <div className="hidden sm:flex items-center gap-1.5">
          <DifficultyDots difficulty={scenario.difficulty} />
          <span className={`text-[11px] font-medium ${diffCfg.textColor} hidden md:inline`}>
            {diffCfg.label}
          </span>
        </div>

        {/* Type badge */}
        <span className={`px-2 py-1 rounded-md text-xs font-semibold border flex items-center gap-1 ${typeCfg.color}`}>
          <TypeIcon size={11} />
          <span className="hidden sm:inline">{typeCfg.label}</span>
        </span>

        {/* Time limit */}
        <span className="text-xs text-surface-500 flex items-center gap-1 w-12 justify-end">
          <Clock size={11} />
          {Math.floor((scenario.time_limit || 900) / 60)}m
        </span>

        {/* Pass rate */}
        {scenario.completion_rate > 0 && (
          <span className="text-[11px] text-surface-600 w-14 text-right hidden lg:block">
            {scenario.completion_rate}% pass
          </span>
        )}

        {/* Best score */}
        {bestScore > 0 && (
          <span className="text-xs text-accent-amber flex items-center gap-1 w-14 justify-end hidden md:flex">
            <Trophy size={11} />
            {bestScore}
          </span>
        )}

        {/* Lock indicator */}
        {scenario.is_accessible === false && (
          <Lock size={13} className="text-surface-600" title="Subscription required" />
        )}

        {/* Bookmark */}
        {isAuthenticated && (
          <button
            onClick={e => onBookmark(e, scenario.id)}
            className="text-surface-600 hover:text-accent-amber transition-colors p-0.5"
            title={scenario.is_bookmarked ? 'Remove bookmark' : 'Bookmark'}
          >
            {scenario.is_bookmarked
              ? <Bookmark size={14} className="text-accent-amber fill-accent-amber" />
              : <BookmarkPlus size={14} />
            }
          </button>
        )}

        {/* Hover arrow */}
        <ChevronRight
          size={15}
          className="text-surface-700 group-hover:text-accent-cyan transition-all duration-200 group-hover:translate-x-0.5"
        />
      </div>
    </Link>
  )
}

function EmptyState({ hasFilters, onClear }) {
  return (
    <div className="glass-card p-16 flex flex-col items-center justify-center text-center animate-fade-in">
      <svg
        width="120" height="90" viewBox="0 0 120 90"
        fill="none" xmlns="http://www.w3.org/2000/svg"
        className="mb-6 opacity-50"
        aria-hidden="true"
      >
        <rect x="8" y="18" width="104" height="60" rx="8"
          stroke="rgb(var(--s-700))" strokeWidth="1.5" strokeDasharray="4 3" />
        <rect x="20" y="32" width="40" height="5" rx="2.5" fill="rgb(var(--s-800))" />
        <rect x="20" y="44" width="64" height="5" rx="2.5" fill="rgb(var(--s-800))" />
        <rect x="20" y="56" width="48" height="5" rx="2.5" fill="rgb(var(--s-800))" />
        <circle cx="92" cy="24" r="16" fill="rgb(var(--s-900))" stroke="rgb(var(--s-700))" strokeWidth="1.5" />
        <path d="M86 24l3.5 3.5L97 18"
          stroke="rgb(var(--s-600))" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        <line x1="102" y1="34" x2="113" y2="45"
          stroke="rgb(var(--s-600))" strokeWidth="2.5" strokeLinecap="round" />
      </svg>
      <h3 className="text-lg font-bold text-white mb-2">No scenarios found</h3>
      <p className="text-surface-400 text-sm max-w-xs mb-6">
        {hasFilters
          ? 'Your current filters returned no results. Try adjusting or clearing them.'
          : 'The catalog is empty right now. Browse technologies to see what’s coming, or try a guided tutorial.'}
      </p>
      {/* An empty state with no exit is a dead end. With filters the fix is to
          clear them; without filters the catalog itself is empty, so send the
          user somewhere that still has content rather than "check back soon". */}
      {hasFilters ? (
        <button onClick={onClear} className="btn-secondary flex items-center gap-2 text-sm">
          <X size={14} /> Clear filters
        </button>
      ) : (
        <div className="flex flex-wrap items-center justify-center gap-3">
          <Link to="/technologies" className="btn-primary flex items-center gap-2 text-sm">
            Browse technologies
          </Link>
          <Link to="/tutorials" className="btn-secondary flex items-center gap-2 text-sm">
            Guided tutorials
          </Link>
        </div>
      )}
    </div>
  )
}

export default function Scenarios() {
  usePageTitle('Scenarios', 'Browse hands-on troubleshooting scenarios across 40+ technologies — each one a real broken system with graded objectives.')
  const [searchParams, setSearchParams] = useSearchParams()
  const { isAuthenticated } = useAuthStore()
  const getTechnologies = useDataStore(s => s.getTechnologies)
  const [scenarios, setScenarios] = useState([])
  const [totalCount, setTotalCount] = useState(0)
  const [loadFailed, setLoadFailed] = useState(false)
  const [technologies, setTechnologies] = useState([])
  const [tags, setTags] = useState([])
  const [loading, setLoading] = useState(true)
  const [showFilters, setShowFilters] = useState(false)

  const PAGE_SIZE = 20
  const currentPage = parseInt(searchParams.get('page') || '1', 10)

  const filters = {
    technology:  searchParams.get('technology')  || '',
    difficulty:  searchParams.get('difficulty')  || '',
    type:        searchParams.get('type')        || '',
    category:    searchParams.get('category')    || '',
    tag:         searchParams.get('tag')         || '',
    search:      searchParams.get('search')      || '',
    // Backend `?free=1` (scenarios.js already forwards it). UI was the missing half of §X7b.
    free:        searchParams.get('free')        || '',
    completed:   searchParams.get('completed')   || '',
    gradeable:   searchParams.get('gradeable')   || '',
  }

  // The `technology` URL param can be either a numeric PK (from the filter
  // chips) or a slug (when linked from a technology page, e.g.
  // /scenarios?technology=vmware). Route it to the matching backend param so
  // the server filters by the right field instead of 500-ing on a slug-as-id.
  const buildQueryFilters = () => {
    const { technology, ...rest } = filters
    const q = { ...rest }
    if (technology) {
      if (/^\d+$/.test(technology)) q.technology = technology
      else q.technology_slug = technology
    }
    return q
  }

  const setFilter = (key, value) => {
    const params = new URLSearchParams(searchParams)
    if (value) params.set(key, value)
    else params.delete(key)
    params.delete('page')
    setSearchParams(params)
  }

  const setPage = (page) => {
    const params = new URLSearchParams(searchParams)
    if (page > 1) params.set('page', page)
    else params.delete('page')
    setSearchParams(params)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const clearFilters = () => setSearchParams({})
  const hasFilters = Object.values(filters).some(Boolean)
  const activeFilterCount = [filters.technology, filters.difficulty, filters.type, filters.category, filters.tag, filters.free, filters.completed, filters.gradeable].filter(Boolean).length

  // The active technology filter may be stored as an id (chips) or a slug
  // (links from a technology page). Match on either so the chip highlights.
  const isTechActive = (tech) =>
    filters.technology === String(tech.id) || filters.technology === tech.slug

  useEffect(() => {
    getTechnologies().then(setTechnologies).catch(console.error)
    scenarioApi.getTags().then(setTags).catch(() => {})
  }, [])

  useEffect(() => {
    setLoading(true)
    scenarioApi.getScenarios({ ...buildQueryFilters(), page: currentPage })
      .then(data => {
        setLoadFailed(false)
        if (data?.results) {
          setScenarios(data.results)
          setTotalCount(data.count || data.results.length)
        } else if (Array.isArray(data)) {
          setScenarios(data)
          setTotalCount(data.length)
        } else {
          setScenarios([])
          setTotalCount(0)
        }
      })
      // A failed fetch previously fell through to the empty state, which now
      // carries a "browse technologies" CTA — that would permanently disguise an
      // outage as an empty catalog. Track it so the error branch wins instead.
      .catch(err => {
        console.error(err)
        setLoadFailed(true)
        setScenarios([])
        setTotalCount(0)
      })
      .finally(() => setLoading(false))
  }, [searchParams.toString()])

  const handleBookmark = async (e, scenarioId) => {
    e.preventDefault()
    e.stopPropagation()
    if (!isAuthenticated) { toast.error('Sign in to bookmark'); return }
    try {
      const result = await scenarioApi.toggleBookmark(scenarioId)
      setScenarios(prev => prev.map(s =>
        s.id === scenarioId ? { ...s, is_bookmarked: result.bookmarked } : s
      ))
      toast.success(result.bookmarked ? 'Bookmarked!' : 'Removed', { duration: 1500 })
    } catch { toast.error('Failed') }
  }

  // Group by difficulty for section layout. Built from DIFFICULTY_ORDER so a new
  // tier shows up automatically; scenarios with a difficulty we don't know about
  // fall into the easiest bucket instead of disappearing from the page.
  const grouped = Object.fromEntries(DIFFICULTY_ORDER.map(k => [k, []]))
  scenarios.forEach(s => {
    (grouped[s.difficulty] || grouped[DIFFICULTY_ORDER[0]]).push(s)
  })

  const { hidden: toolbarHidden, toolbarRef, anchorRef } = useScrollHideToolbar(64)

  return (
    <div className="max-w-6xl mx-auto animate-fade-in">
      <PageHeader
        eyebrow="Training"
        title="Scenarios"
        subtitle={loading ? 'Loading…' : `${totalCount} challenge${totalCount !== 1 ? 's' : ''}`}
      />

      <StickyPageToolbar hidden={toolbarHidden} toolbarRef={toolbarRef} className="mb-2">
        <div className="flex items-center justify-end gap-1.5 flex-wrap mb-2">
          <div className="flex items-center gap-1.5 flex-wrap">
            {Object.entries(difficultyConfig).map(([key, cfg]) => {
              const count = grouped[key]?.length ?? 0
              if (!count && !loading) return null
              return (
                <button
                  key={key}
                  onClick={() => setFilter('difficulty', filters.difficulty === key ? '' : key)}
                  className={`flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-semibold border transition-all ${
                    filters.difficulty === key ? cfg.badge : 'bg-surface-800/60 text-surface-400 border-surface-700/60 hover:text-white'
                  }`}
                >
                  <DifficultyDots difficulty={key} />
                  {cfg.label}
                  {!loading && <span className="opacity-50">({count})</span>}
                </button>
              )
            })}
          </div>
        </div>

        <div className="flex items-center gap-2">
          <div className="relative flex-1">
            <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-surface-500 pointer-events-none" />
            <input
              type="text"
              placeholder="Search scenarios…"
              value={filters.search}
              onChange={e => setFilter('search', e.target.value)}
              className="input-field pl-8 py-1.5 text-sm w-full"
            />
            {filters.search && (
              <button onClick={() => setFilter('search', '')} className="absolute right-3 top-1/2 -translate-y-1/2 text-surface-500 hover:text-white">
                <X size={13} />
              </button>
            )}
          </div>

          <button
            onClick={() => setShowFilters(p => !p)}
            className={`relative flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium border transition-all shrink-0 ${
              showFilters || hasFilters
                ? 'bg-accent-cyan/10 text-accent-cyan border-accent-cyan/20'
                : 'bg-surface-800 text-surface-400 hover:text-white border-surface-700'
            }`}
          >
            <Filter size={14} />
            <span className="hidden sm:inline">Filters</span>
            {activeFilterCount > 0 && (
              <span className="absolute -top-1.5 -right-1.5 w-4 h-4 rounded-full bg-accent-cyan text-surface-950 text-[10px] font-bold flex items-center justify-center leading-none">
                {activeFilterCount}
              </span>
            )}
          </button>

          {hasFilters && (
            <button onClick={clearFilters} className="text-xs text-surface-500 hover:text-accent-red transition-colors px-2 py-1 shrink-0">
              Clear all
            </button>
          )}
        </div>
      </StickyPageToolbar>
      <div ref={anchorRef} className="h-px w-full -mt-px" aria-hidden="true" />

      <div className="space-y-5">
      {showFilters && (
        <div className="glass-card p-5 space-y-5 animate-slide-up border border-surface-700/50">

          {/* Technology */}
          <div>
            <p className="text-[11px] font-semibold text-surface-500 uppercase tracking-widest mb-3">Technology</p>
            <div className="flex gap-2 flex-wrap">
              <button
                onClick={() => setFilter('technology', '')}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all ${
                  !filters.technology
                    ? 'bg-accent-cyan/10 text-accent-cyan border-accent-cyan/20'
                    : 'bg-surface-800 text-surface-400 hover:text-white border-surface-700'
                }`}
              >
                All
              </button>
              {technologies.map(tech => (
                <button
                  key={tech.id}
                  onClick={() => setFilter('technology', isTechActive(tech) ? '' : String(tech.id))}
                  className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all ${
                    isTechActive(tech)
                      ? 'bg-accent-cyan/10 text-accent-cyan border-accent-cyan/20'
                      : 'bg-surface-800 text-surface-400 hover:text-white border-surface-700'
                  }`}
                >
                  <TechIcon name={tech.name} />
                  {tech.name}
                  {tech.scenario_count > 0 && (
                    <span className="text-surface-600 text-[10px]">({tech.scenario_count})</span>
                  )}
                </button>
              ))}
            </div>
          </div>

          {/* Difficulty + Type + Access */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
            <div>
              <p className="text-[11px] font-semibold text-surface-500 uppercase tracking-widest mb-3">Difficulty</p>
              <div className="flex gap-2 flex-wrap">
                {Object.entries(difficultyConfig).map(([key, cfg]) => (
                  <button
                    key={key}
                    type="button"
                    onClick={() => setFilter('difficulty', filters.difficulty === key ? '' : key)}
                    className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all ${
                      filters.difficulty === key ? cfg.badge : 'bg-surface-800 text-surface-400 hover:text-white border-surface-700'
                    }`}
                  >
                    <DifficultyDots difficulty={key} />
                    {cfg.label}
                  </button>
                ))}
              </div>
            </div>
            <div>
              <p className="text-[11px] font-semibold text-surface-500 uppercase tracking-widest mb-3">Type</p>
              <div className="flex gap-2 flex-wrap">
                {Object.entries(typeConfig).map(([key, cfg]) => {
                  const Icon = cfg.icon
                  return (
                    <button
                      key={key}
                      type="button"
                      onClick={() => setFilter('type', filters.type === key ? '' : key)}
                      className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all ${
                        filters.type === key ? cfg.color : 'bg-surface-800 text-surface-400 hover:text-white border-surface-700'
                      }`}
                    >
                      <Icon size={12} /> {cfg.label}
                    </button>
                  )
                })}
              </div>
            </div>
          </div>

          <div>
            <p className="text-[11px] font-semibold text-surface-500 uppercase tracking-widest mb-3">Access</p>
            <div className="flex gap-2 flex-wrap">
              <button
                type="button"
                onClick={() => setFilter('free', filters.free === '1' ? '' : '1')}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all ${
                  filters.free === '1'
                    ? 'bg-accent-green/10 text-accent-green border-accent-green/20'
                    : 'bg-surface-800 text-surface-400 hover:text-white border-surface-700'
                }`}
              >
                Free only
              </button>
              <button
                type="button"
                onClick={() => setFilter('free', filters.free === '0' ? '' : '0')}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all ${
                  filters.free === '0'
                    ? 'bg-accent-cyan/10 text-accent-cyan border-accent-cyan/20'
                    : 'bg-surface-800 text-surface-400 hover:text-white border-surface-700'
                }`}
              >
                Paid only
              </button>
              <button
                type="button"
                onClick={() => setFilter('gradeable', filters.gradeable === '1' ? '' : '1')}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all ${
                  filters.gradeable === '1'
                    ? 'bg-accent-green/10 text-accent-green border-accent-green/20'
                    : 'bg-surface-800 text-surface-400 hover:text-white border-surface-700'
                }`}
              >
                Gradeable
              </button>
              <button
                type="button"
                onClick={() => setFilter('gradeable', filters.gradeable === '0' ? '' : '0')}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all ${
                  filters.gradeable === '0'
                    ? 'bg-accent-amber/10 text-accent-amber border-accent-amber/20'
                    : 'bg-surface-800 text-surface-400 hover:text-white border-surface-700'
                }`}
              >
                Ungradeable
              </button>
            </div>
          </div>

          {isAuthenticated && (
            <div>
              <p className="text-[11px] font-semibold text-surface-500 uppercase tracking-widest mb-3">Progress</p>
              <div className="flex gap-2 flex-wrap">
                <button
                  type="button"
                  onClick={() => setFilter('completed', filters.completed === '1' ? '' : '1')}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all ${
                    filters.completed === '1'
                      ? 'bg-accent-green/10 text-accent-green border-accent-green/20'
                      : 'bg-surface-800 text-surface-400 hover:text-white border-surface-700'
                  }`}
                >
                  Solved
                </button>
                <button
                  type="button"
                  onClick={() => setFilter('completed', filters.completed === '0' ? '' : '0')}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all ${
                    filters.completed === '0'
                      ? 'bg-accent-amber/10 text-accent-amber border-accent-amber/20'
                      : 'bg-surface-800 text-surface-400 hover:text-white border-surface-700'
                  }`}
                >
                  Unsolved
                </button>
              </div>
            </div>
          )}

          {/* Tags */}
          {tags.length > 0 && (
            <div>
              <p className="text-[11px] font-semibold text-surface-500 uppercase tracking-widest mb-3">Tags</p>
              <div className="flex gap-1.5 flex-wrap">
                {tags.slice(0, 24).map(tag => (
                  <button
                    key={tag.slug}
                    onClick={() => setFilter('tag', filters.tag === tag.slug ? '' : tag.slug)}
                    className={`flex items-center gap-1 px-2 py-1 rounded text-[11px] font-medium border transition-all ${
                      filters.tag === tag.slug
                        ? 'bg-accent-purple/10 text-accent-purple border-accent-purple/20'
                        : 'bg-surface-800 text-surface-500 hover:text-surface-300 border-transparent'
                    }`}
                  >
                    <Hash size={9} /> {tag.name}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── Results ── (isolation-isolate + z-0 keeps cards behind the sticky toolbar) */}
      <div className="relative isolate">
      {loading ? (
        <div className="glass-card overflow-hidden divide-y divide-surface-800/50">
          {[...Array(8)].map((_, i) => (
            <div key={i} className="flex items-center gap-4 px-5 py-4 border-l-2 border-l-surface-800 animate-pulse">
              <div className="w-8 shrink-0 space-y-1.5">
                <div className="h-3 w-5 bg-surface-800 rounded mx-auto" />
                <div className="w-3 h-3 rounded-full bg-surface-800 mx-auto" />
              </div>
              <div className="flex-1 space-y-2">
                <div className="h-4 bg-surface-800 rounded w-2/5" />
                <div className="h-3 bg-surface-800/60 rounded w-3/5" />
              </div>
              <div className="flex items-center gap-3">
                <div className="h-6 w-20 bg-surface-800 rounded-md hidden sm:block" />
                <div className="h-6 w-14 bg-surface-800 rounded-md" />
                <div className="h-4 w-10 bg-surface-800 rounded" />
              </div>
            </div>
          ))}
        </div>
      ) : scenarios.length === 0 ? (
        loadFailed ? (
          <div
            data-testid="scenarios-load-error"
            className="glass-card p-16 flex flex-col items-center justify-center text-center animate-fade-in"
          >
            <AlertTriangle size={32} className="text-accent-red mb-4" />
            <h3 className="text-lg font-bold text-white mb-2">Couldn&apos;t load scenarios</h3>
            <p className="text-surface-400 text-sm max-w-xs mb-6">
              The catalog isn&apos;t empty — this request failed. Try again in a moment.
            </p>
            <button onClick={() => window.location.reload()} className="btn-secondary text-sm">
              Retry
            </button>
          </div>
        ) : (
          <EmptyState hasFilters={hasFilters} onClear={clearFilters} />
        )
      ) : (
        <div className="space-y-8 animate-fade-in">
          {Object.entries(grouped).map(([difficulty, items]) => {
            if (items.length === 0) return null
            const cfg = difficultyConfig[difficulty]
            return (
              <section key={difficulty}>
                {/* Section divider header */}
                <div className="flex items-center gap-3 mb-3 px-1">
                  <div className={`w-1.5 h-1.5 rounded-full shrink-0 ${cfg.dot}`} />
                  <h2 className={`text-[11px] font-bold uppercase tracking-widest ${cfg.textColor}`}>
                    {cfg.label}
                  </h2>
                  <span className="text-[11px] text-surface-600 bg-surface-800 px-2 py-0.5 rounded-full font-medium">
                    {items.length}
                  </span>
                  <div className="flex-1 h-px bg-surface-800/80" />
                </div>

                <div className="glass-card overflow-hidden divide-y divide-surface-800/40">
                  {items.map((scenario, i) => (
                    <ScenarioCard
                      key={scenario.id}
                      scenario={scenario}
                      index={i}
                      isAuthenticated={isAuthenticated}
                      onBookmark={handleBookmark}
                    />
                  ))}
                </div>
              </section>
            )
          })}
        </div>
      )}

      {/* ── Pagination ── */}
      {!loading && totalCount > PAGE_SIZE && (
        <div className="pt-2">
          <Pagination
            currentPage={currentPage}
            totalPages={Math.ceil(totalCount / PAGE_SIZE)}
            onPageChange={setPage}
          />
        </div>
      )}
      </div>{/* end isolate wrapper */}
      </div>{/* end scroll content */}
    </div>
  )
}
