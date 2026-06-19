import { useState, useEffect } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { scenarioApi } from '../api/scenarios'
import {
  ChevronLeft, Target, CheckCircle2, Lock, ChevronRight,
  Wrench, Play, Skull, FolderKanban, Clock, Layers, ChevronDown, ChevronUp,
  BookOpen, Trophy, AlertCircle, Circle, BarChart3
} from 'lucide-react'
import toast from 'react-hot-toast'
import StickyPageToolbar from '../components/StickyPageToolbar'
import { PageHeader } from '../components/design'

const difficultyConfig = {
  easy:   { label: 'Easy',   bg: 'bg-green-500/10 text-green-400 border-green-500/20' },
  medium: { label: 'Medium', bg: 'bg-amber-500/10 text-amber-400 border-amber-500/20' },
  hard:   { label: 'Hard',   bg: 'bg-red-500/10 text-red-400 border-red-500/20' },
}

const projectDifficulty = {
  beginner:     { label: 'Beginner',     color: 'text-green-400',  dot: 'bg-green-500' },
  intermediate: { label: 'Intermediate', color: 'text-amber-400',  dot: 'bg-amber-500' },
  advanced:     { label: 'Advanced',     color: 'text-red-400',    dot: 'bg-red-500' },
}

const archLabel = {
  '2tier':          '2-Tier Architecture',
  '3tier':          '3-Tier Architecture',
  'microservices':  'Microservices',
  'cicd':           'CI/CD Pipeline',
  'custom':         'Custom Project',
}

const typeIcons = { fix: Wrench, do: Play, hack: Skull }

function ProjectCard({ project, onStart }) {
  const [expanded, setExpanded] = useState(false)
  const diff = projectDifficulty[project.difficulty] || projectDifficulty.intermediate
  const done = project.user_progress?.status === 'completed'
  const started = !!project.user_progress
  const completedTasks = project.tasks?.filter(t => t.user_status === 'done').length || 0
  const totalTasks = project.task_count || project.tasks?.length || 0
  const pct = totalTasks ? Math.round((completedTasks / totalTasks) * 100) : 0

  return (
    <div className={`rounded-2xl border transition-all duration-200 overflow-hidden ${
      done
        ? 'border-green-500/30 bg-green-500/5'
        : started
        ? 'border-accent-cyan/30 bg-accent-cyan/5'
        : 'border-surface-700/60 bg-surface-900/40 hover:border-accent-cyan/30'
    }`}>
      {/* Project header */}
      <div className="p-5">
        <div className="flex items-start gap-4">
          {/* Icon */}
          <div className={`w-11 h-11 rounded-xl flex items-center justify-center shrink-0 ${
            done ? 'bg-green-500/20' : 'bg-gradient-to-br from-accent-cyan/20 to-accent-purple/20 border border-accent-cyan/20'
          }`}>
            {done
              ? <CheckCircle2 size={22} className="text-green-400" />
              : <FolderKanban size={22} className="text-accent-cyan" />
            }
          </div>
          {/* Title and meta */}
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap mb-1">
              <h3 className="text-base font-bold text-white leading-tight">{project.title}</h3>
              {done && <span className="text-[10px] font-bold bg-green-500/15 text-green-400 border border-green-500/30 px-2 py-0.5 rounded-full">COMPLETED</span>}
              {started && !done && <span className="text-[10px] font-bold bg-accent-cyan/15 text-accent-cyan border border-accent-cyan/30 px-2 py-0.5 rounded-full">IN PROGRESS</span>}
            </div>
            <p className="text-sm text-surface-400 line-clamp-2">{project.description}</p>
          </div>
        </div>

        {/* Meta row */}
        <div className="flex flex-wrap items-center gap-3 mt-4 text-xs text-surface-500">
          <span className={`flex items-center gap-1 font-medium ${diff.color}`}>
            <span className={`w-1.5 h-1.5 rounded-full ${diff.dot}`} />
            {diff.label}
          </span>
          <span className="flex items-center gap-1">
            <Clock size={11} /> ~{project.estimated_hours}h
          </span>
          <span className="flex items-center gap-1">
            <Layers size={11} /> {archLabel[project.architecture_type] || project.architecture_type}
          </span>
          <span className="flex items-center gap-1">
            <BookOpen size={11} /> {totalTasks} tasks
          </span>
        </div>

        {/* Progress bar if started */}
        {started && totalTasks > 0 && (
          <div className="mt-3">
            <div className="flex justify-between text-[11px] text-surface-500 mb-1">
              <span>{completedTasks}/{totalTasks} tasks done</span>
              <span>{pct}%</span>
            </div>
            <div className="h-1.5 bg-surface-800 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all ${done ? 'bg-green-500' : 'bg-accent-cyan'}`}
                style={{ width: `${pct}%` }}
              />
            </div>
          </div>
        )}

        {/* Action row */}
        <div className="flex items-center gap-2 mt-4">
          <button
            type="button"
            onClick={() => onStart(project)}
            className={`text-xs font-semibold px-4 py-2 rounded-lg border transition-all ${
              done
                ? 'border-green-500/30 text-green-400 hover:bg-green-500/10'
                : started
                ? 'border-accent-cyan/40 bg-accent-cyan/10 text-accent-cyan hover:bg-accent-cyan/20'
                : 'border-accent-cyan/40 bg-accent-cyan/10 text-accent-cyan hover:bg-accent-cyan/20'
            }`}
          >
            {done ? 'View Project' : started ? 'Continue Project' : 'Start Project'}
          </button>
          <button
            type="button"
            onClick={() => setExpanded(e => !e)}
            className="text-xs text-surface-500 hover:text-white flex items-center gap-1 px-3 py-2"
          >
            {expanded ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
            {expanded ? 'Hide tasks' : 'Preview tasks'}
          </button>
        </div>
      </div>

      {/* Expanded task list */}
      {expanded && project.tasks?.length > 0 && (
        <div className="border-t border-surface-800/60 bg-surface-950/40">
          <div className="p-4 space-y-2">
            {project.tasks.map((task, i) => {
              const taskDone = task.user_status === 'done'
              const taskActive = task.user_status === 'in_progress'
              return (
                <div key={task.id} className={`flex items-center gap-3 p-2.5 rounded-lg text-sm ${
                  taskDone ? 'bg-green-500/5 border border-green-500/15' : 'border border-surface-800/50'
                }`}>
                  <div className="w-5 shrink-0">
                    {taskDone
                      ? <CheckCircle2 size={15} className="text-green-400" />
                      : taskActive
                      ? <Circle size={15} className="text-accent-cyan fill-accent-cyan/20" />
                      : <Circle size={15} className="text-surface-600" />
                    }
                  </div>
                  <span className="text-[10px] font-bold text-surface-500 font-mono w-16 shrink-0">{task.jira_key}</span>
                  <span className={`flex-1 font-medium ${taskDone ? 'line-through text-surface-500' : 'text-white'}`}>
                    {task.title}
                  </span>
                  {task.depends_on && i > 0 && <AlertCircle size={12} className="text-surface-600" title="Has dependency" />}
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}

export default function TechnologyDetail() {
  const { slug } = useParams()
  const navigate = useNavigate()
  const [techDetail, setTechDetail] = useState(null)
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState('scenarios')

  useEffect(() => {
    if (!slug) return
    setLoading(true)
    scenarioApi.getTechnologyDetail(slug)
      .then(data => {
        setTechDetail(data)
        // Auto-switch to projects tab if no scenarios but has projects
        if (!data.scenarios?.length && data.projects?.length) {
          setActiveTab('projects')
        }
      })
      .catch(() => {
        toast.error('Failed to load technology')
        navigate('/technologies')
      })
      .finally(() => setLoading(false))
  }, [slug, navigate])

  const handleStartProject = async (project) => {
    try {
      const { default: api } = await import('../api/client')
      await api.post(`/projects/${project.id}/start/`)
      toast.success(`Project started: ${project.title}`)
      // Refresh to get updated progress
      const data = await scenarioApi.getTechnologyDetail(slug)
      setTechDetail(data)
      setActiveTab('projects')
    } catch {
      toast.error('Could not start project. Please log in.')
    }
  }

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
  const projects = techDetail.projects || []
  const scenarios = techDetail.scenarios || []
  const hasProjects = projects.length > 0
  const hasScenarios = scenarios.length > 0

  const tabs = [
    { id: 'scenarios', label: 'Scenarios', count: scenarios.length, icon: Target },
    ...(hasProjects ? [{ id: 'projects', label: 'Projects', count: projects.length, icon: FolderKanban }] : []),
  ]

  return (
    <div className="max-w-5xl mx-auto space-y-4 animate-fade-in">
      <PageHeader
        eyebrow="Learning paths"
        title={tech.name}
        subtitle={tech.description}
      />

      <StickyPageToolbar className="space-y-3">
        <button type="button" onClick={() => navigate('/technologies')} className="text-sm text-surface-400 hover:text-accent-cyan flex items-center gap-1">
          <ChevronLeft size={16} /> All technologies
        </button>
        <div className="glass-card p-6">
          <div className="flex items-center gap-2 flex-wrap">
              {tech.difficulty_counts && Object.entries(tech.difficulty_counts).map(([diff, count]) =>
                count > 0 ? (
                  <div key={diff} className={`px-3 py-1.5 rounded-lg text-xs font-medium border ${difficultyConfig[diff]?.bg || ''}`}>
                    {difficultyConfig[diff]?.label}: {count}
                  </div>
                ) : null
              )}
              {hasProjects && (
                <div className="px-3 py-1.5 rounded-lg text-xs font-medium border border-accent-purple/30 bg-accent-purple/10 text-accent-purple">
                  <FolderKanban size={11} className="inline mr-1" />{projects.length} Project{projects.length !== 1 ? 's' : ''}
                </div>
              )}
          </div>

          {/* Tabs */}
          {hasProjects && (
            <div className="flex gap-1 mt-5 border-b border-surface-800/50">
              {tabs.map(tab => {
                const Icon = tab.icon
                return (
                  <button
                    key={tab.id}
                    type="button"
                    onClick={() => setActiveTab(tab.id)}
                    className={`flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium border-b-2 -mb-px transition-colors ${
                      activeTab === tab.id
                        ? tab.id === 'projects'
                          ? 'border-accent-purple text-accent-purple'
                          : 'border-accent-cyan text-accent-cyan'
                        : 'border-transparent text-surface-500 hover:text-white'
                    }`}
                  >
                    <Icon size={14} />
                    {tab.label}
                    <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-bold ${
                      activeTab === tab.id
                        ? tab.id === 'projects' ? 'bg-accent-purple/20' : 'bg-accent-cyan/20'
                        : 'bg-surface-800'
                    }`}>
                      {tab.count}
                    </span>
                  </button>
                )
              })}
            </div>
          )}
        </div>
      </StickyPageToolbar>

      {/* Scenarios tab */}
      {activeTab === 'scenarios' && (
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
              const diffScenarios = scenarios.filter(s => s.difficulty === difficulty)
              if (!diffScenarios.length) return null
              return (
                <div key={difficulty}>
                  <div className="px-6 py-3 bg-surface-900/50">
                    <h2 className="text-sm font-semibold text-surface-400 uppercase tracking-wider flex items-center gap-2">
                      <span className={`w-2 h-2 rounded-full ${
                        difficulty === 'easy' ? 'bg-green-500' : difficulty === 'medium' ? 'bg-amber-500' : 'bg-red-500'
                      }`} />
                      {difficultyConfig[difficulty].label}
                      <span className="text-surface-600 font-normal">({diffScenarios.length})</span>
                    </h2>
                  </div>
                  {diffScenarios.map((scenario, index) => {
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

          {!hasScenarios && (
            <div className="p-12 text-center">
              <Target size={32} className="mx-auto text-surface-700 mb-3" />
              <p className="text-surface-400">No scenarios available for this technology yet.</p>
            </div>
          )}
        </div>
      )}

      {/* Projects tab */}
      {activeTab === 'projects' && (
        <div className="space-y-4">
          {/* Projects header callout */}
          <div className="rounded-xl border border-accent-purple/25 bg-gradient-to-r from-accent-purple/8 to-accent-cyan/5 p-4 flex items-start gap-3">
            <FolderKanban size={20} className="text-accent-purple shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-semibold text-white">End-to-End Projects</p>
              <p className="text-xs text-surface-400 mt-0.5">
                Build real architectures step-by-step. Each project is guided by Jira tickets — open them in the AI lab, complete the tasks, and ask the Jira bot if you get stuck.
              </p>
            </div>
          </div>

          {projects.map(project => (
            <ProjectCard key={project.id} project={project} onStart={handleStartProject} />
          ))}

          {!hasProjects && (
            <div className="glass-card p-12 text-center">
              <FolderKanban size={32} className="mx-auto text-surface-700 mb-3" />
              <p className="text-surface-400">No projects available for this technology yet. Check back soon!</p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
