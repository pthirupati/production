import { useState, useEffect } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { scenarioApi } from '../api/scenarios'
import {
  ChevronLeft, Target, CheckCircle2, Lock, ChevronRight,
  Wrench, Play, Skull
} from 'lucide-react'
import toast from 'react-hot-toast'
import StickyPageToolbar from '../components/StickyPageToolbar'

const difficultyConfig = {
  easy: { label: 'Easy', bg: 'bg-green-500/10 text-green-400' },
  medium: { label: 'Medium', bg: 'bg-amber-500/10 text-amber-400' },
  hard: { label: 'Hard', bg: 'bg-red-500/10 text-red-400' },
}

const typeIcons = { fix: Wrench, do: Play, hack: Skull }

export default function TechnologyDetail() {
  const { slug } = useParams()
  const navigate = useNavigate()
  const [techDetail, setTechDetail] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!slug) return
    setLoading(true)
    scenarioApi.getTechnologyDetail(slug)
      .then(setTechDetail)
      .catch(() => {
        toast.error('Failed to load technology')
        navigate('/technologies')
      })
      .finally(() => setLoading(false))
  }, [slug, navigate])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-2 border-accent-cyan border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  if (!techDetail) return null

  if (techDetail.coming_soon || techDetail.technology?.coming_soon) {
    return (
      <div className="max-w-3xl mx-auto space-y-4">
        <button type="button" onClick={() => navigate('/technologies')} className="text-sm text-surface-400 hover:text-accent-cyan flex items-center gap-1">
          <ChevronLeft size={16} /> All technologies
        </button>
        <div className="glass-card p-12 text-center">
          <Lock size={32} className="mx-auto text-accent-amber mb-3" />
          <h1 className="text-xl font-bold text-white mb-2">{techDetail.technology?.name} — Coming Soon</h1>
          <p className="text-surface-400">Scenarios and labs for this technology are not available yet.</p>
        </div>
      </div>
    )
  }

  const tech = techDetail.technology

  return (
    <div className="max-w-5xl mx-auto space-y-4 animate-fade-in">
      <StickyPageToolbar className="space-y-3">
      <button type="button" onClick={() => navigate('/technologies')} className="text-sm text-surface-400 hover:text-accent-cyan flex items-center gap-1">
        <ChevronLeft size={16} /> All technologies
      </button>
      <div className="glass-card p-6">
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <div className="min-w-0">
            <h1 className="text-xl sm:text-2xl font-bold text-white truncate">{tech.name}</h1>
            <p className="text-sm text-surface-400 mt-1 max-w-xl">{tech.description}</p>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            {tech.difficulty_counts && Object.entries(tech.difficulty_counts).map(([diff, count]) => (
              count > 0 && (
                <div key={diff} className={`px-3 py-1.5 rounded-lg text-xs font-medium ${difficultyConfig[diff]?.bg || ''}`}>
                  {difficultyConfig[diff]?.label}: {count}
                </div>
              )
            ))}
          </div>
        </div>
      </div>
      </StickyPageToolbar>

      <div className="glass-card p-0 overflow-hidden">
        {tech.learning_path?.length > 0 && (
          <div className="px-6 py-4 border-b border-surface-800/50 bg-surface-900/30">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-semibold text-white">Recommended learning path</h2>
              {tech.learning_path_progress?.steps_total > 0 && (
                <span className="text-xs text-accent-cyan">
                  {tech.learning_path_progress.steps_completed}/{tech.learning_path_progress.steps_total} complete
                </span>
              )}
            </div>
            <ol className="space-y-2">
              {tech.learning_path.map((step, i) => {
                const done = tech.learning_path_progress?.completed_slugs?.includes(step.scenario_slug)
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

        <div className="divide-y divide-surface-800/30">
          {['easy', 'medium', 'hard'].map(difficulty => {
            const scenarios = techDetail.scenarios.filter(s => s.difficulty === difficulty)
            if (scenarios.length === 0) return null
            return (
              <div key={difficulty}>
                <div className="px-6 py-3 bg-surface-900/50">
                  <h2 className="text-sm font-semibold text-surface-400 uppercase tracking-wider flex items-center gap-2">
                    <span className={`w-2 h-2 rounded-full ${
                      difficulty === 'easy' ? 'bg-green-500' : difficulty === 'medium' ? 'bg-amber-500' : 'bg-red-500'
                    }`} />
                    {difficultyConfig[difficulty].label}
                    <span className="text-surface-600 font-normal">({scenarios.length})</span>
                  </h2>
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
          </div>
        )}
      </div>
    </div>
  )
}
