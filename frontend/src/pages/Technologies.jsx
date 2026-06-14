import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { scenarioApi } from '../api/scenarios'
import {
  Server, Cloud, Globe, Monitor, Database, Cpu,
  ChevronRight, Target, CheckCircle2, Lock, Layers,
  ArrowRight, Wrench, Play, Skull, Shield
} from 'lucide-react'
import toast from 'react-hot-toast'

const techIcons = {
  Linux: Server,
  Docker: Monitor,
  Networking: Globe,
  'Web Servers': Globe,
  Databases: Database,
  AWS: Cloud,
  Kubernetes: Cpu,
  Security: Shield,
  'GPU & NVIDIA': Cpu,
}

const techColors = {
  cyan: 'from-cyan-500/20 to-cyan-600/5 border-cyan-500/20 text-cyan-400',
  blue: 'from-blue-500/20 to-blue-600/5 border-blue-500/20 text-blue-400',
  green: 'from-green-500/20 to-green-600/5 border-green-500/20 text-green-400',
  amber: 'from-amber-500/20 to-amber-600/5 border-amber-500/20 text-amber-400',
  purple: 'from-purple-500/20 to-purple-600/5 border-purple-500/20 text-purple-400',
  red: 'from-red-500/20 to-red-600/5 border-red-500/20 text-red-400',
}

const difficultyConfig = {
  easy: { label: 'Easy', color: 'badge-easy', bg: 'bg-green-500/10 text-green-400' },
  medium: { label: 'Medium', color: 'badge-medium', bg: 'bg-amber-500/10 text-amber-400' },
  hard: { label: 'Hard', color: 'badge-hard', bg: 'bg-red-500/10 text-red-400' },
}

const typeIcons = { fix: Wrench, do: Play, hack: Skull }

export default function Technologies() {
  const [technologies, setTechnologies] = useState([])
  const [selectedTech, setSelectedTech] = useState(null)
  const [techDetail, setTechDetail] = useState(null)
  const [loading, setLoading] = useState(true)
  const [detailLoading, setDetailLoading] = useState(false)

  useEffect(() => {
    scenarioApi.getTechnologies()
      .then(data => {
        setTechnologies(data)
        const available = data.filter(t => !t.coming_soon)
        if (available.length > 0) {
          setSelectedTech(available[0].slug)
          setDetailLoading(true)
          scenarioApi.getTechnologyDetail(available[0].slug)
            .then(setTechDetail)
            .catch(() => toast.error('Failed to load technology details'))
            .finally(() => setDetailLoading(false))
        } else if (data.length > 0) {
          loadTechnology(data[0].slug, true, data[0])
        }
      })
      .catch(() => toast.error('Failed to load technologies'))
      .finally(() => setLoading(false))
  }, [])

  const loadTechnology = async (slug, isComingSoon = false, techMeta = null) => {
    setSelectedTech(slug)
    if (isComingSoon) {
      const tech = techMeta || technologies.find(t => t.slug === slug) || { slug, name: slug, coming_soon: true }
      setTechDetail({ technology: tech, scenarios: [], coming_soon: true })
      setDetailLoading(false)
      return
    }
    setDetailLoading(true)
    try {
      const data = await scenarioApi.getTechnologyDetail(slug)
      setTechDetail(data)
    } catch {
      toast.error('Failed to load technology details')
    } finally {
      setDetailLoading(false)
    }
  }

  if (loading) return (
    <div className="flex items-center justify-center h-64">
      <div className="w-8 h-8 border-2 border-accent-cyan border-t-transparent rounded-full animate-spin" />
    </div>
  )

  const comingSoonTechs = technologies.filter(t => t.coming_soon)
  const availableTechs = technologies.filter(t => !t.coming_soon)
  const sortedTechnologies = [...availableTechs, ...comingSoonTechs]

  return (
    <div className="max-w-7xl mx-auto space-y-6 animate-fade-in">
      {/* Header */}
      <div className="relative overflow-hidden glass-card p-8 mb-6">
        <div className="absolute inset-0 bg-gradient-to-r from-accent-cyan/8 via-transparent to-accent-purple/8" />
        <div className="absolute inset-0 bg-dots-pattern opacity-20" />
        <div className="relative flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-black text-white tracking-tight flex items-center gap-3">
              <Layers size={24} className="text-accent-cyan" />
              <span className="bg-gradient-to-r from-accent-cyan to-accent-purple bg-clip-text text-transparent">Technologies</span>
            </h1>
            <p className="text-surface-400 mt-2">
              Choose a technology to explore its challenges
            </p>
          </div>
          <Link to="/scenarios" className="text-sm text-surface-400 hover:text-accent-cyan transition-colors flex items-center gap-1">
            View All Scenarios <ArrowRight size={14} />
          </Link>
        </div>
      </div>

      {/* Technology cards grid */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
        {sortedTechnologies.map(tech => {
          const Icon = techIcons[tech.name] || Server
          const colorClass = techColors[tech.color] || techColors.cyan
          const isSelected = selectedTech === tech.slug
          if (tech.coming_soon) {
            return (
              <button
                key={tech.id}
                type="button"
                onClick={() => loadTechnology(tech.slug, true, tech)}
                className={`relative p-5 rounded-xl border border-dashed transition-all duration-200 text-left ${
                  isSelected
                    ? 'border-surface-600 bg-surface-800/40 opacity-70'
                    : 'border-surface-700/50 bg-surface-900/30 opacity-50 hover:opacity-65'
                }`}
              >
                <Icon size={28} className="mb-3 text-surface-600" />
                <h3 className="text-base font-semibold text-surface-500 mb-1">{tech.name}</h3>
                <span className="text-xs text-accent-amber font-medium">Coming soon</span>
                <p className="text-[10px] text-surface-600 mt-2">Preview only — not available yet</p>
              </button>
            )
          }
          return (
            <button
              key={tech.id}
              onClick={() => loadTechnology(tech.slug, false)}
              className={`relative p-5 rounded-xl border transition-all duration-200 text-left group ${
                isSelected
                  ? `bg-gradient-to-br ${colorClass} border-opacity-100 ring-1 ring-current/20 scale-[1.02]`
                  : 'bg-surface-800/50 border-surface-700/50 hover:border-surface-600 hover:bg-surface-800'
              }`}
            >
              <Icon size={28} className={`mb-3 ${isSelected ? '' : 'text-surface-400 group-hover:text-accent-cyan'} transition-colors`} />
              <h3 className="text-base font-semibold text-white mb-1">{tech.name}</h3>
              <div className="flex items-center gap-2">
                <span className="text-xs text-surface-500">
                  {tech.scenario_count || 0} scenario{tech.scenario_count !== 1 ? 's' : ''}
                </span>
              </div>
              {isSelected && (
                <div className="absolute top-2 right-2 w-2 h-2 rounded-full bg-current animate-pulse" />
              )}
            </button>
          )
        })}
      </div>

      {/* Selected technology detail */}
      {selectedTech && (
        <div className="glass-card p-0 overflow-hidden animate-fade-in">
          {detailLoading ? (
            <div className="flex items-center justify-center h-48">
              <div className="w-6 h-6 border-2 border-accent-cyan border-t-transparent rounded-full animate-spin" />
            </div>
          ) : techDetail?.coming_soon || techDetail?.technology?.coming_soon ? (
            <div className="p-12 text-center">
              <Lock size={32} className="mx-auto text-accent-amber mb-3" />
              <h2 className="text-xl font-bold text-white mb-2">{techDetail.technology?.name || 'Technology'} — Coming Soon</h2>
              <p className="text-surface-400 max-w-md mx-auto">
                This technology is on our roadmap. You can preview it here, but scenarios and labs are not available yet.
              </p>
              {techDetail.technology?.description && (
                <p className="text-sm text-surface-500 mt-4 max-w-lg mx-auto">{techDetail.technology.description}</p>
              )}
            </div>
          ) : techDetail ? (
            <>
              {/* Tech header */}
              <div className="p-6 border-b border-surface-800/50">
                <div className="flex items-center justify-between">
                  <div>
                    <h2 className="text-xl font-bold text-white">{techDetail.technology.name}</h2>
                    <p className="text-sm text-surface-400 mt-1 max-w-xl">{techDetail.technology.description}</p>
                  </div>
                  <div className="flex items-center gap-3">
                    {techDetail.technology.difficulty_counts && Object.entries(techDetail.technology.difficulty_counts).map(([diff, count]) => (
                      count > 0 && (
                        <div key={diff} className={`px-3 py-1.5 rounded-lg text-xs font-medium ${difficultyConfig[diff]?.bg || ''}`}>
                          {difficultyConfig[diff]?.label}: {count}
                        </div>
                      )
                    ))}
                  </div>
                </div>
              </div>

              {techDetail.technology.learning_path?.length > 0 && (
                <div className="px-6 py-4 border-b border-surface-800/50 bg-surface-900/30">
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="text-sm font-semibold text-white">Recommended learning path</h3>
                    {techDetail.technology.learning_path_progress?.steps_total > 0 && (
                      <span className="text-xs text-accent-cyan">
                        {techDetail.technology.learning_path_progress.steps_completed}/
                        {techDetail.technology.learning_path_progress.steps_total} complete
                      </span>
                    )}
                  </div>
                  <ol className="space-y-2">
                    {techDetail.technology.learning_path.map((step, i) => {
                      const done = techDetail.technology.learning_path_progress?.completed_slugs?.includes(step.scenario_slug)
                      return (
                      <li key={i} className="flex items-start gap-3 text-sm">
                        <span className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold shrink-0 ${
                          done ? 'bg-accent-green/20 text-accent-green' : 'bg-accent-cyan/10 text-accent-cyan'
                        }`}>{done ? '✓' : i + 1}</span>
                        <div>
                          <p className="text-white font-medium">{step.title || step.scenario_slug}</p>
                          {step.description && <p className="text-surface-500 text-xs mt-0.5">{step.description}</p>}
                          {step.scenario_slug && (
                            <Link to={`/scenarios/${step.scenario_slug}`} className="text-accent-cyan text-xs hover:underline mt-1 inline-block">
                              Open scenario →
                            </Link>
                          )}
                        </div>
                      </li>
                      )
                    })}
                  </ol>
                </div>
              )}

              {/* Scenarios list grouped by difficulty */}
              <div className="divide-y divide-surface-800/30">
                {['easy', 'medium', 'hard'].map(difficulty => {
                  const scenarios = techDetail.scenarios.filter(s => s.difficulty === difficulty)
                  if (scenarios.length === 0) return null
                  return (
                    <div key={difficulty}>
                      <div className="px-6 py-3 bg-surface-900/50">
                        <h3 className="text-sm font-semibold text-surface-400 uppercase tracking-wider flex items-center gap-2">
                          <span className={`w-2 h-2 rounded-full ${
                            difficulty === 'easy' ? 'bg-green-500' : difficulty === 'medium' ? 'bg-amber-500' : 'bg-red-500'
                          }`} />
                          {difficultyConfig[difficulty].label}
                          <span className="text-surface-600 font-normal">({scenarios.length})</span>
                        </h3>
                      </div>
                      {scenarios.map((scenario, index) => {
                        const TypeIcon = typeIcons[scenario.scenario_type] || Wrench
                        const isCompleted = scenario.user_progress?.completed
                        return (
                          <Link
                            key={scenario.id}
                            to={`/scenarios/${scenario.slug}`}
                            className="flex items-center gap-4 px-6 py-3.5 hover:bg-surface-800/30 transition-colors group"
                          >
                            <span className="text-xs text-surface-600 w-6 text-right font-mono">{index + 1}</span>
                            <div className="w-5">
                              {isCompleted ? (
                                <CheckCircle2 size={16} className="text-accent-green" />
                              ) : scenario.user_progress?.attempts > 0 ? (
                                <div className="w-4 h-4 rounded-full border-2 border-accent-amber" />
                              ) : (
                                <div className="w-4 h-4 rounded-full border border-surface-700" />
                              )}
                            </div>
                            <div className="flex-1 min-w-0">
                              <span className="text-sm font-medium text-white group-hover:text-accent-cyan transition-colors truncate block">
                                {scenario.title}
                              </span>
                              {scenario.subtitle && (
                                <span className="text-xs text-surface-500 block truncate">{scenario.subtitle}</span>
                              )}
                            </div>
                            <span className="text-xs text-surface-500 flex items-center gap-1 w-16 shrink-0">
                              <Target size={11} /> {Math.floor((scenario.time_limit || 900) / 60)}m
                            </span>
                            <TypeIcon size={14} className="text-surface-500 shrink-0" />
                            {scenario.user_progress?.best_score > 0 && (
                              <span className="text-xs text-accent-amber font-medium w-12 text-right shrink-0">
                                {scenario.user_progress.best_score} pts
                              </span>
                            )}
                            {scenario.is_accessible === false && (
                              <Lock size={12} className="text-surface-600 shrink-0" title="Subscription required" />
                            )}
                            <ChevronRight size={14} className="text-surface-700 group-hover:text-surface-400 transition-colors shrink-0" />
                          </Link>
                        )
                      })}
                    </div>
                  )
                })}
              </div>

              {techDetail.scenarios.length === 0 && (
                <div className="p-12 text-center">
                  <Target size={32} className="mx-auto text-surface-700 mb-3" />
                  <p className="text-surface-400">No scenarios available for this technology yet.</p>
                  <p className="text-sm text-surface-500 mt-1">Check back soon!</p>
                </div>
              )}
            </>
          ) : null}
        </div>
      )}
    </div>
  )
}
