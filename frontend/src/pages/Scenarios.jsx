import { useState, useEffect, useCallback } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { scenarioApi } from '../api/scenarios'
import { useAuthStore } from '../store/authStore'
import { useDataStore } from '../store/dataStore'
import {
  Search, CheckCircle2, Server, Clock, Wrench, Play, Skull,
  BookmarkPlus, Bookmark, Filter, X, Hash, ChevronDown, Trophy, Lock
} from 'lucide-react'
import toast from 'react-hot-toast'
import Pagination from '../components/Pagination'
import StickyPageToolbar from '../components/StickyPageToolbar'

const typeConfig = {
  fix: { icon: Wrench, label: 'Fix', color: 'bg-accent-cyan/10 text-accent-cyan border-accent-cyan/20' },
  do:  { icon: Play, label: 'Do', color: 'bg-accent-green/10 text-accent-green border-accent-green/20' },
  hack: { icon: Skull, label: 'Hack', color: 'bg-accent-red/10 text-accent-red border-accent-red/20' },
}

const difficultyConfig = {
  easy: { label: 'Easy', color: 'badge-easy' },
  medium: { label: 'Medium', color: 'badge-medium' },
  hard: { label: 'Hard', color: 'badge-hard' },
}

export default function Scenarios() {
  const [searchParams, setSearchParams] = useSearchParams()
  const { isAuthenticated } = useAuthStore()
  const getTechnologies = useDataStore(s => s.getTechnologies)
  const [scenarios, setScenarios] = useState([])
  const [totalCount, setTotalCount] = useState(0)
  const [technologies, setTechnologies] = useState([])
  const [tags, setTags] = useState([])
  const [loading, setLoading] = useState(true)
  const [showFilters, setShowFilters] = useState(false)

  const PAGE_SIZE = 20
  const currentPage = parseInt(searchParams.get('page') || '1', 10)

  const filters = {
    technology: searchParams.get('technology') || '',
    difficulty: searchParams.get('difficulty') || '',
    type: searchParams.get('type') || '',
    tag: searchParams.get('tag') || '',
    search: searchParams.get('search') || '',
  }

  const setFilter = (key, value) => {
    const params = new URLSearchParams(searchParams)
    if (value) params.set(key, value)
    else params.delete(key)
    params.delete('page') // Reset to page 1 on filter change
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

  useEffect(() => {
    getTechnologies().then(techs => setTechnologies(techs)).catch(console.error)
    scenarioApi.getTags().then(setTags).catch(() => {})
  }, [])

  useEffect(() => {
    setLoading(true)
    scenarioApi.getScenarios({ ...filters, page: currentPage })
      .then(data => {
        // Handle both paginated { count, results } and flat array responses
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
      .catch(console.error)
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

  // Group scenarios by difficulty for SadServers-style layout
  const grouped = { easy: [], medium: [], hard: [] }
  scenarios.forEach(s => {
    if (grouped[s.difficulty]) grouped[s.difficulty].push(s)
  })

  const activeCount = totalCount

  return (
    <div className="max-w-6xl mx-auto space-y-4 animate-fade-in">
      {/* Header — scrolls with page */}
      <div className="relative overflow-hidden glass-card p-5 sm:p-6 gradient-border">
        <div className="absolute inset-0 bg-gradient-to-r from-accent-purple/8 via-transparent to-accent-cyan/8 pointer-events-none" />
        <div className="relative flex items-center justify-between gap-3">
          <div className="min-w-0">
            <h1 className="text-2xl sm:text-3xl font-black text-white tracking-tight">Scenarios</h1>
            <p className="text-surface-400 mt-0.5 text-sm">
              {activeCount} challenge{activeCount !== 1 && 's'} available
            </p>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            {hasFilters && (
              <button onClick={clearFilters} className="text-xs text-surface-500 hover:text-accent-red transition-colors px-2 py-1">
                Clear
              </button>
            )}
            <button
              onClick={() => setShowFilters(!showFilters)}
              className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-all ${
                showFilters || hasFilters
                  ? 'bg-accent-cyan/10 text-accent-cyan border border-accent-cyan/20'
                  : 'bg-surface-800 text-surface-400 hover:text-white border border-transparent'
              }`}
            >
              <Filter size={14} />
              Filters
              {hasFilters && <span className="w-1.5 h-1.5 rounded-full bg-accent-cyan" />}
            </button>
          </div>
        </div>
      </div>

      {/* Sticky search bar — only this sticks on scroll */}
      <StickyPageToolbar>
        <div className="flex items-center gap-2">
          <div className="relative flex-1">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-surface-500" />
            <input
              type="text"
              placeholder="Search scenarios..."
              value={filters.search}
              onChange={(e) => setFilter('search', e.target.value)}
              className="input-field pl-10 py-2.5 text-sm w-full"
            />
            {filters.search && (
              <button onClick={() => setFilter('search', '')} className="absolute right-3 top-1/2 -translate-y-1/2 text-surface-500 hover:text-white">
                <X size={14} />
              </button>
            )}
          </div>
          {hasFilters && (
            <span className="text-xs text-accent-cyan bg-accent-cyan/10 border border-accent-cyan/20 px-2 py-1 rounded-lg whitespace-nowrap">
              {[filters.technology && 'Tech', filters.difficulty, filters.type, filters.tag && 'Tag'].filter(Boolean).join(' · ')}
            </span>
          )}
        </div>
      </StickyPageToolbar>

      {/* Filter panel */}
      {showFilters && (
        <div className="glass-card p-5 space-y-4 animate-fade-in">
          {/* Technologies */}
          <div>
            <label className="text-xs font-semibold text-surface-400 uppercase tracking-wider mb-2 block">Technology</label>
            <div className="flex gap-2 flex-wrap">
              <button
                onClick={() => setFilter('technology', '')}
                className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${
                  !filters.technology ? 'bg-accent-cyan/10 text-accent-cyan border border-accent-cyan/20' : 'text-surface-400 hover:text-white bg-surface-800'
                }`}
              >All</button>
              {technologies.map((tech) => (
                <button
                  key={tech.id}
                  onClick={() => setFilter('technology', filters.technology === String(tech.id) ? '' : String(tech.id))}
                  className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-all flex items-center gap-1.5 ${
                    filters.technology === String(tech.id)
                      ? 'bg-accent-cyan/10 text-accent-cyan border border-accent-cyan/20'
                      : 'text-surface-400 hover:text-white bg-surface-800'
                  }`}
                >
                  <Server size={13} />
                  {tech.name}
                  <span className="text-xs opacity-60">({tech.scenario_count})</span>
                </button>
              ))}
            </div>
          </div>

          {/* Difficulty + Type */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-xs font-semibold text-surface-400 uppercase tracking-wider mb-2 block">Difficulty</label>
              <div className="flex gap-2">
                {Object.entries(difficultyConfig).map(([key, { label, color }]) => (
                  <button
                    key={key}
                    onClick={() => setFilter('difficulty', filters.difficulty === key ? '' : key)}
                    className={`px-3 py-1.5 rounded-lg text-sm font-medium capitalize transition-all ${
                      filters.difficulty === key ? color : 'text-surface-400 hover:text-white bg-surface-800'
                    }`}
                  >{label}</button>
                ))}
              </div>
            </div>
            <div>
              <label className="text-xs font-semibold text-surface-400 uppercase tracking-wider mb-2 block">Type</label>
              <div className="flex gap-2">
                {Object.entries(typeConfig).map(([key, { icon: Icon, label, color }]) => (
                  <button
                    key={key}
                    onClick={() => setFilter('type', filters.type === key ? '' : key)}
                    className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-all flex items-center gap-1.5 border ${
                      filters.type === key ? color : 'text-surface-400 hover:text-white bg-surface-800 border-transparent'
                    }`}
                  ><Icon size={13} /> {label}</button>
                ))}
              </div>
            </div>
          </div>

          {/* Tags */}
          {tags.length > 0 && (
            <div>
              <label className="text-xs font-semibold text-surface-400 uppercase tracking-wider mb-2 block">Tags</label>
              <div className="flex gap-2 flex-wrap">
                {tags.slice(0, 20).map((tag) => (
                  <button
                    key={tag.slug}
                    onClick={() => setFilter('tag', filters.tag === tag.slug ? '' : tag.slug)}
                    className={`px-2.5 py-1 rounded text-xs font-medium transition-all flex items-center gap-1 ${
                      filters.tag === tag.slug
                        ? 'bg-accent-purple/10 text-accent-purple border border-accent-purple/20'
                        : 'text-surface-500 hover:text-surface-300 bg-surface-800'
                    }`}
                  ><Hash size={10} /> {tag.name}</button>
                ))}
              </div>
            </div>
          )}

          {hasFilters && (
            <button onClick={clearFilters} className="text-xs text-surface-500 hover:text-accent-red transition-colors flex items-center gap-1">
              <X size={12} /> Clear all filters
            </button>
          )}
        </div>
      )}

      {/* Results */}
      {loading ? (
        <div className="flex items-center justify-center h-40">
          <div className="w-8 h-8 border-2 border-accent-cyan border-t-transparent rounded-full animate-spin" />
        </div>
      ) : scenarios.length === 0 ? (
        <div className="text-center py-16">
          <Server size={48} className="mx-auto text-surface-600 mb-4" />
          <p className="text-surface-400 mb-2">No scenarios found</p>
          {hasFilters && (
            <button onClick={clearFilters} className="text-accent-cyan text-sm hover:underline">Clear filters</button>
          )}
        </div>
      ) : (
        /* SadServers-style grouped layout */
        <div className="space-y-8">
          {Object.entries(grouped).map(([difficulty, items]) => {
            if (items.length === 0) return null
            const config = difficultyConfig[difficulty]
            return (
              <div key={difficulty}>
                <div className="flex items-center gap-3 mb-4">
                  <h2 className="text-lg font-bold text-white">{config.label}</h2>
                  <span className="text-xs text-surface-500 bg-surface-800 px-2 py-0.5 rounded">
                    {items.length}
                  </span>
                </div>

                {/* Table-style rows */}
                <div className="glass-card overflow-hidden divide-y divide-surface-800/50">
                  {items.map((scenario, index) => {
                    const TypeIcon = typeConfig[scenario.scenario_type]?.icon || Wrench
                    const typeColor = typeConfig[scenario.scenario_type]?.color || typeConfig.fix.color
                    return (
                      <Link
                        key={scenario.id}
                        to={`/scenarios/${scenario.slug}`}
                        className="flex items-center gap-4 px-5 py-3.5 hover:bg-surface-800/30 transition-colors group"
                      >
                        {/* Number */}
                        <span className="text-xs text-surface-600 w-6 text-right font-mono">{index + 1}</span>

                        {/* Completed check */}
                        <div className="w-5">
                          {scenario.user_progress?.completed ? (
                            <CheckCircle2 size={16} className="text-accent-green" />
                          ) : scenario.user_progress?.attempts > 0 ? (
                            <div className="w-4 h-4 rounded-full border-2 border-accent-amber" />
                          ) : null}
                        </div>

                        {/* Title + subtitle */}
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-medium text-white group-hover:text-accent-cyan transition-colors truncate">
                              {scenario.title}
                            </span>
                            {scenario.subtitle && (
                              <span className="text-xs text-surface-500 hidden lg:inline truncate">
                                — {scenario.subtitle}
                              </span>
                            )}
                          </div>
                        </div>

                        {/* Time */}
                        <span className="text-xs text-surface-500 flex items-center gap-1 w-16">
                          <Clock size={11} />
                          {Math.floor((scenario.time_limit || 900) / 60)} m
                        </span>

                        {/* Type badge */}
                        <span className={`px-2 py-0.5 rounded text-xs font-medium border flex items-center gap-1 ${typeColor}`}>
                          <TypeIcon size={11} />
                          {typeConfig[scenario.scenario_type]?.label || 'Fix'}
                        </span>

                        {scenario.interview_mode && (
                          <span className="px-2 py-0.5 rounded text-[10px] font-medium bg-accent-purple/10 text-accent-purple border border-accent-purple/20">
                            Interview
                          </span>
                        )}

                        {scenario.completion_rate > 0 && (
                          <span className="text-[10px] text-surface-500 w-14 text-right" title="Global success rate">
                            {scenario.completion_rate}% pass
                          </span>
                        )}

                        {/* Tags */}
                        <div className="hidden md:flex gap-1 w-32">
                          {(scenario.tags || []).slice(0, 2).map(tag => (
                            <span key={tag.slug} className="text-[10px] text-surface-500 bg-surface-800 px-1.5 py-0.5 rounded">
                              {tag.name}
                            </span>
                          ))}
                        </div>

                        {/* Score */}
                        {scenario.user_progress?.best_score > 0 && (
                          <span className="text-xs text-accent-amber flex items-center gap-1 w-16">
                            <Trophy size={11} />
                            {scenario.user_progress.best_score}
                          </span>
                        )}

                        {/* Lock for non-accessible paid scenarios */}
                        {scenario.is_accessible === false && (
                          <Lock size={13} className="text-surface-600 shrink-0" title="Subscription required" />
                        )}

                        {/* Bookmark */}
                        {isAuthenticated && (
                          <button
                            onClick={(e) => handleBookmark(e, scenario.id)}
                            className="text-surface-600 hover:text-accent-amber transition-colors"
                          >
                            {scenario.is_bookmarked
                              ? <Bookmark size={14} className="text-accent-amber fill-accent-amber" />
                              : <BookmarkPlus size={14} />
                            }
                          </button>
                        )}

                        {/* Actions */}
                        <div className="flex gap-2">
                          <span className="text-xs text-surface-500 hover:text-white px-2 py-1 rounded bg-surface-800 opacity-0 group-hover:opacity-100 transition-opacity">
                            Info
                          </span>
                          <span className="text-xs text-accent-cyan px-2 py-1 rounded bg-accent-cyan/10 border border-accent-cyan/20 opacity-0 group-hover:opacity-100 transition-opacity">
                            Run
                          </span>
                        </div>
                      </Link>
                    )
                  })}
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* Pagination */}
      {!loading && totalCount > PAGE_SIZE && (
        <Pagination
          currentPage={currentPage}
          totalPages={Math.ceil(totalCount / PAGE_SIZE)}
          onPageChange={setPage}
        />
      )}
    </div>
  )
}
