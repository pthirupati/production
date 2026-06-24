import { useState, useEffect, useMemo } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { motion } from 'framer-motion'
import { scenarioApi } from '../api/scenarios'
import {
  ChevronLeft, Target, CheckCircle2, Lock, ChevronRight,
  Wrench, Play, Skull, FolderKanban, Clock, Layers, ChevronDown, ChevronUp,
  BookOpen, AlertCircle, Circle, Award, PlayCircle,
} from 'lucide-react'
import toast from 'react-hot-toast'
import TechIcon from '../components/marketing/TechIcon'
import FxPanel from '../ui/FxPanel'
import FxStatCard from '../ui/FxStatCard'
import ScrollReveal from '../ui/ScrollReveal'
import { fadeUp, staggerContainer, viewportOnce } from '../ui/motion'
import { useAuthStore } from '../store/authStore'

const difficultyConfig = {
  easy:   { label: 'Easy',   color: '#56e0b0', bg: 'rgba(86,224,176,.12)' },
  medium: { label: 'Medium', color: '#feb155', bg: 'rgba(254,177,85,.12)' },
  hard:   { label: 'Hard',   color: '#ec6a5e', bg: 'rgba(236,106,94,.12)' },
}

const projectDifficulty = {
  beginner:     { label: 'Beginner',     color: 'text-green-400',  dot: 'bg-green-500' },
  intermediate: { label: 'Intermediate', color: 'text-amber-400',  dot: 'bg-amber-500' },
  advanced:     { label: 'Advanced',     color: 'text-red-400',    dot: 'bg-red-500' },
}

const archLabel = {
  '2tier': '2-Tier Architecture',
  '3tier': '3-Tier Architecture',
  microservices: 'Microservices',
  cicd: 'CI/CD Pipeline',
  custom: 'Custom Project',
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
    <FxPanel padding="p-0" className="overflow-hidden hover:border-white/[0.14] transition-colors">
      <div className="p-5">
        <div className="flex items-start gap-4">
          <div className={`w-11 h-11 rounded-xl flex items-center justify-center shrink-0 ${
            done ? 'bg-green-500/20' : 'bg-accent-cyan/15 border border-accent-cyan/20'
          }`}>
            {done ? <CheckCircle2 size={22} className="text-green-400" /> : <FolderKanban size={22} className="text-accent-cyan" />}
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap mb-1">
              <h3 className="text-base font-bold text-white leading-tight">{project.title}</h3>
              {done && <span className="text-[10px] font-bold bg-green-500/15 text-green-400 border border-green-500/30 px-2 py-0.5 rounded-full">COMPLETED</span>}
              {started && !done && <span className="text-[10px] font-bold bg-accent-cyan/15 text-accent-cyan border border-accent-cyan/30 px-2 py-0.5 rounded-full">IN PROGRESS</span>}
            </div>
            <p className="text-sm text-white/50 line-clamp-2">{project.description}</p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-3 mt-4 text-xs text-white/45">
          <span className={`flex items-center gap-1 font-medium ${diff.color}`}>
            <span className={`w-1.5 h-1.5 rounded-full ${diff.dot}`} />
            {diff.label}
          </span>
          <span className="flex items-center gap-1"><Clock size={11} /> ~{project.estimated_hours}h</span>
          <span className="flex items-center gap-1"><Layers size={11} /> {archLabel[project.architecture_type] || project.architecture_type}</span>
          <span className="flex items-center gap-1"><BookOpen size={11} /> {totalTasks} tasks</span>
        </div>
        {started && totalTasks > 0 && (
          <div className="mt-3">
            <div className="flex justify-between text-[11px] text-white/45 mb-1">
              <span>{completedTasks}/{totalTasks} tasks done</span>
              <span>{pct}%</span>
            </div>
            <div className="h-1.5 bg-white/[0.06] rounded-full overflow-hidden">
              <div className={`h-full rounded-full transition-all ${done ? 'bg-green-500' : 'bg-gradient-to-r from-accent-cyan to-accent-green'}`} style={{ width: `${pct}%` }} />
            </div>
          </div>
        )}
        <div className="flex items-center gap-2 mt-4">
          <button
            type="button"
            onClick={() => onStart(project)}
            className="text-xs font-semibold px-4 py-2 rounded-lg border border-accent-cyan/40 bg-accent-cyan/10 text-accent-cyan hover:bg-accent-cyan/20 transition-all"
          >
            {done ? 'View Project' : started ? 'Continue Project' : 'Start Project'}
          </button>
          <button type="button" onClick={() => setExpanded(e => !e)} className="text-xs text-white/45 hover:text-white flex items-center gap-1 px-3 py-2">
            {expanded ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
            {expanded ? 'Hide tasks' : 'Preview tasks'}
          </button>
        </div>
      </div>
      {expanded && project.tasks?.length > 0 && (
        <div className="border-t border-white/[0.06] bg-black/20 p-4 space-y-2">
          {project.tasks.map((task, i) => {
            const taskDone = task.user_status === 'done'
            const taskActive = task.user_status === 'in_progress'
            return (
              <div key={task.id} className={`flex items-center gap-3 p-2.5 rounded-lg text-sm ${taskDone ? 'bg-green-500/5 border border-green-500/15' : 'border border-white/[0.06]'}`}>
                <div className="w-5 shrink-0">
                  {taskDone ? <CheckCircle2 size={15} className="text-green-400" /> : taskActive ? <Circle size={15} className="text-accent-cyan fill-accent-cyan/20" /> : <Circle size={15} className="text-white/25" />}
                </div>
                <span className="text-[10px] font-bold text-white/40 font-mono w-16 shrink-0">{task.jira_key}</span>
                <span className={`flex-1 font-medium ${taskDone ? 'line-through text-white/40' : 'text-white'}`}>{task.title}</span>
                {task.depends_on && i > 0 && <AlertCircle size={12} className="text-white/30" title="Has dependency" />}
              </div>
            )
          })}
        </div>
      )}
    </FxPanel>
  )
}

function groupScenariosByCategory(scenarios) {
  const groups = {}
  for (const s of scenarios) {
    const cat = s.category || 'General'
    if (!groups[cat]) groups[cat] = []
    groups[cat].push(s)
  }
  return Object.entries(groups).map(([name, items]) => ({ name, items }))
}

export default function TechnologyDetail() {
  const { slug } = useParams()
  const navigate = useNavigate()
  const { isAuthenticated } = useAuthStore()
  const [techDetail, setTechDetail] = useState(null)
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState('scenarios')

  useEffect(() => {
    if (!slug) return
    setLoading(true)
    scenarioApi.getTechnologyDetail(slug)
      .then(data => {
        setTechDetail(data)
        if (!data.scenarios?.length && data.projects?.length) setActiveTab('projects')
      })
      .catch(() => {
        toast.error('Failed to load technology')
        navigate('/technologies')
      })
      .finally(() => setLoading(false))
  }, [slug, navigate])

  const handleStartProject = async (project) => {
    try {
      const { default: apiClient } = await import('../api/client')
      const { data: started } = await apiClient.post(`/projects/${project.id}/start/`)
      // If the project has a launchable environment, open its lab (terminal /
      // simulation / IDE / VMware / Grafana) so the user can actually work on it.
      if (started?.lab_scenario_id) {
        try {
          const { labApi } = await import('../api/labs')
          const session = await labApi.startLab(started.lab_scenario_id)
          toast.success(`Project workspace ready: ${project.title}`)
          navigate(`/lab/${session.id}`, { state: { techSlug: slug } })
          return
        } catch (e) {
          // Tell the user why the workspace didn't open instead of silently
          // dropping to the checklist (e.g. a subscription-gated lab).
          if (e?.response?.status === 403) {
            toast.error(e.response?.data?.error || 'Subscribe to this technology to open the project workspace.')
          }
          // Fall through to the checklist view if the environment can't start.
        }
      }
      toast.success(`Project started: ${project.title}`)
      const data = await scenarioApi.getTechnologyDetail(slug)
      setTechDetail(data)
      setActiveTab('projects')
    } catch {
      toast.error('Could not start project. Please log in.')
    }
  }

  const stats = useMemo(() => {
    if (!techDetail) return null
    const scenarios = techDetail.scenarios || []
    const completed = scenarios.filter(s => s.user_progress?.completed).length
    const scores = scenarios.filter(s => s.user_progress?.best_score > 0).map(s => s.user_progress.best_score)
    const avg = scores.length ? Math.round(scores.reduce((a, b) => a + b, 0) / scores.length) : 0
    return { total: scenarios.length, completed, avg }
  }, [techDetail])

  const progressPct = useMemo(() => {
    const lp = techDetail?.technology?.learning_path_progress
    if (lp?.steps_total > 0) return Math.round((lp.steps_completed / lp.steps_total) * 100)
    if (stats?.total) return Math.round((stats.completed / stats.total) * 100)
    return 0
  }, [techDetail, stats])

  const modules = useMemo(() => {
    if (!techDetail?.scenarios?.length) return []
    return groupScenariosByCategory(techDetail.scenarios).map(({ name, items }) => {
      const done = items.filter(s => s.user_progress?.completed).length
      const total = items.length
      const pct = total ? Math.round((done / total) * 100) : 0
      const level = items.some(s => s.difficulty === 'hard') ? 'Advanced' : items.some(s => s.difficulty === 'medium') ? 'Intermediate' : 'Beginner'
      return { name, items, done, total, pct, level }
    })
  }, [techDetail])

  const skills = useMemo(() => {
    const cats = techDetail?.technology?.categories || []
    const tags = new Set(cats.filter(Boolean))
    for (const s of techDetail?.scenarios || []) {
      if (s.category) tags.add(s.category)
      for (const t of s.tags || []) tags.add(t.name)
    }
    return [...tags].slice(0, 12)
  }, [techDetail])

  const isSubscribed = useMemo(() => {
    const scenarios = techDetail?.scenarios || []
    const paid = scenarios.filter(s => !s.is_free)
    if (!paid.length) return false
    return paid.some(s => s.is_accessible !== false)
  }, [techDetail])

  if (loading) {
    return (
      <div className="flex flex-col gap-5 animate-pulse">
        <div className="h-48 rounded-[20px] bg-white/[0.04]" />
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map(i => <div key={i} className="h-24 rounded-2xl bg-white/[0.04]" />)}
        </div>
        <div className="h-64 rounded-[18px] bg-white/[0.04]" />
      </div>
    )
  }

  if (!techDetail) return null

  if (techDetail.coming_soon || techDetail.technology?.coming_soon) {
    return (
      <div className="space-y-4">
        <Link to="/technologies" className="text-sm text-white/55 hover:text-accent-cyan flex items-center gap-1.5 font-semibold">
          <ChevronLeft size={16} /> All technologies
        </Link>
        <FxPanel className="text-center py-16">
          <Lock size={32} className="mx-auto text-accent-amber mb-3" />
          <h1 className="text-xl font-bold text-white mb-2">{techDetail.technology?.name} — Coming Soon</h1>
          <p className="text-white/50">Scenarios and labs for this technology are not available yet.</p>
        </FxPanel>
      </div>
    )
  }

  const tech = techDetail.technology
  const projects = techDetail.projects || []
  const scenarios = techDetail.scenarios || []
  const certTracks = techDetail.cert_tracks || []
  const hasProjects = projects.length > 0
  const hasScenarios = scenarios.length > 0
  const popularScenarios = [...scenarios].slice(0, 8)
  // "Continue learning" jumps straight into the next scenario IN THIS technology
  // (first uncompleted, else the first), keeping the user in-context instead of
  // bouncing out to the global all-scenarios grid.
  const nextScenario = scenarios.find(s => !s.user_progress?.completed) || scenarios[0]

  return (
    <motion.div
      className="flex flex-col gap-[22px] pb-8"
      variants={staggerContainer}
      initial="hidden"
      animate="visible"
    >
      {/* Page header row */}
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <Link to="/technologies" className="flex items-center gap-1.5 text-[13px] font-semibold text-white/60 hover:text-white transition-colors">
          <ChevronLeft size={15} /> All technologies
        </Link>
        {isAuthenticated && isSubscribed && (
          <span className="text-[11.5px] font-semibold px-3 py-1.5 rounded-lg bg-accent-green/12 text-accent-green border border-accent-green/20">
            Subscribed
          </span>
        )}
      </div>

      {/* Hero */}
      <ScrollReveal variant={fadeUp}>
        <div className="relative overflow-hidden rounded-[20px] p-7 sm:p-8 border border-white/[0.09] bg-[radial-gradient(120%_140%_at_100%_0%,#1a2d5e_0%,#15102f_55%,#0c0e1c_100%)]">
          <div aria-hidden className="absolute -top-12 left-8 w-[280px] h-[200px] bg-accent-cyan/20 blur-[42px] rounded-full pointer-events-none" />
          <div className="relative flex items-start gap-5 flex-wrap">
            <span
              className="w-16 h-16 rounded-[18px] flex items-center justify-center shrink-0"
              style={{ background: `${tech.color || '#49b5ff'}22`, color: tech.color || '#49b5ff' }}
            >
              <TechIcon slug={tech.slug} icon={tech.icon} size={32} />
            </span>
            <div className="flex-1 min-w-[240px]">
              <h1 className="font-display font-extrabold text-[28px] sm:text-[30px] tracking-tight text-white m-0">{tech.name}</h1>
              <p className="text-[14.5px] text-white/60 mt-2.5 leading-relaxed max-w-xl">{tech.description}</p>
              {hasScenarios && (
                <div className="mt-[18px] max-w-md">
                  <div className="flex justify-between text-xs text-white/55 mb-1.5">
                    <span>Your progress</span>
                    <span>{stats?.completed || 0} / {stats?.total || 0} labs · {progressPct}%</span>
                  </div>
                  <div className="h-[9px] rounded-md bg-white/[0.06] overflow-hidden">
                    <motion.div
                      className="h-full rounded-md bg-gradient-to-r from-accent-cyan to-accent-green"
                      initial={{ width: 0 }}
                      animate={{ width: `${progressPct}%` }}
                      transition={{ duration: 1, ease: [0.2, 0.8, 0.2, 1] }}
                    />
                  </div>
                </div>
              )}
            </div>
            <div className="flex flex-col gap-2.5 items-stretch sm:items-end w-full sm:w-auto">
              <Link
                to={nextScenario ? `/scenarios/${nextScenario.slug}` : hasScenarios ? `/scenarios?technology=${tech.slug}` : '/pricing'}
                className="inline-flex items-center justify-center gap-2 px-[18px] py-3 rounded-[11px] text-[13.5px] font-bold text-white bg-gradient-to-br from-accent-cyan to-accent-purple shadow-[0_8px_22px_-8px_rgb(var(--a-cyan))] hover:opacity-95 transition-opacity"
              >
                <PlayCircle size={14} /> Continue learning
              </Link>
              {!isSubscribed && isAuthenticated && (
                <Link to="/pricing" className="text-center text-[11.5px] text-white/45 hover:text-accent-cyan">Subscribe to unlock all labs</Link>
              )}
            </div>
          </div>
        </div>
      </ScrollReveal>

      {/* Stats */}
      {hasScenarios && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3.5">
          <FxStatCard value={stats?.total || 0} label="Total labs" color="#fff" delay={0} />
          <FxStatCard value={stats?.completed || 0} label="Solved" color="#56e0b0" delay={0.05} />
          <FxStatCard value={stats?.avg || '—'} label="Avg score" color="#49b5ff" delay={0.1} />
          <FxStatCard value={tech.scenario_count || stats?.total || 0} label="In catalog" color="#b266e0" delay={0.15} />
        </div>
      )}

      {/* Learning path modules */}
      {modules.length > 0 && (
        <ScrollReveal>
          <FxPanel padding="p-6">
            <h3 className="font-display font-bold text-base text-white m-0 mb-4">Learning path</h3>
            <div className="flex flex-col gap-3">
              {modules.map((mod, idx) => (
                <motion.div
                  key={mod.name}
                  variants={fadeUp}
                  initial="hidden"
                  whileInView="visible"
                  viewport={viewportOnce}
                  transition={{ delay: idx * 0.05 }}
                  className="flex items-center gap-4 p-4 rounded-[13px] bg-white/[0.03] border border-white/[0.07] flex-wrap"
                >
                  <span className="w-[38px] h-[38px] rounded-[11px] flex items-center justify-center shrink-0 bg-accent-cyan/12 text-accent-cyan">
                    <BookOpen size={18} />
                  </span>
                  <div className="flex-1 min-w-[180px]">
                    <p className="text-sm font-semibold text-white m-0 capitalize">{mod.name}</p>
                    <p className="text-xs text-white/45 mt-0.5">{mod.total} labs · {mod.level}</p>
                  </div>
                  <div className="w-[130px] min-w-[130px]">
                    <div className="flex justify-between text-[11px] text-white/50 mb-1">
                      <span>{mod.done}/{mod.total}</span>
                      <span>{mod.pct}%</span>
                    </div>
                    <div className="h-1.5 rounded bg-white/[0.06] overflow-hidden">
                      <div className="h-full rounded bg-gradient-to-r from-accent-cyan to-accent-purple" style={{ width: `${mod.pct}%` }} />
                    </div>
                  </div>
                  <Link
                    to={`/scenarios?technology=${tech.slug}&category=${encodeURIComponent(mod.name)}`}
                    className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-[9px] text-xs font-semibold text-accent-cyan bg-accent-cyan/10 border border-accent-cyan/25 hover:bg-accent-cyan/15 transition-colors"
                  >
                    {mod.pct === 100 ? 'Review' : mod.done > 0 ? 'Continue' : 'Start'}
                  </Link>
                </motion.div>
              ))}
            </div>
          </FxPanel>
        </ScrollReveal>
      )}

      {/* Tabs when projects exist */}
      {hasProjects && (
        <div className="flex gap-1 border-b border-white/[0.08]">
          {[
            { id: 'scenarios', label: 'Scenarios', count: scenarios.length, icon: Target },
            { id: 'projects', label: 'Projects', count: projects.length, icon: FolderKanban },
          ].map(tab => {
            const Icon = tab.icon
            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium border-b-2 -mb-px transition-colors ${
                  activeTab === tab.id ? 'border-accent-cyan text-accent-cyan' : 'border-transparent text-white/45 hover:text-white'
                }`}
              >
                <Icon size={14} /> {tab.label}
                <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-bold ${activeTab === tab.id ? 'bg-accent-cyan/20' : 'bg-white/[0.06]'}`}>
                  {tab.count}
                </span>
              </button>
            )
          })}
        </div>
      )}

      {activeTab === 'scenarios' && (
        <div className="grid lg:grid-cols-[1.6fr_1fr] gap-[22px] items-start">
          <FxPanel padding="p-6">
            <h3 className="font-display font-bold text-base text-white m-0 mb-4">Popular scenarios</h3>
            {popularScenarios.length > 0 ? (
              <div className="flex flex-col">
                {popularScenarios.map(scenario => {
                  const TypeIcon = typeIcons[scenario.scenario_type] || Wrench
                  const isCompleted = scenario.user_progress?.completed
                  const inProgress = scenario.user_progress?.attempts > 0 && !isCompleted
                  const diff = difficultyConfig[scenario.difficulty] || difficultyConfig.medium
                  return (
                    <Link
                      key={scenario.id}
                      to={`/scenarios/${scenario.slug}`}
                      className="flex items-center gap-3.5 py-3 px-3 -mx-3 rounded-[11px] hover:bg-white/[0.03] transition-colors group"
                    >
                      <span
                        className="w-[30px] h-[30px] rounded-lg flex items-center justify-center shrink-0"
                        style={{ background: isCompleted ? 'rgba(86,224,176,.12)' : inProgress ? 'rgba(254,177,85,.12)' : 'rgba(255,255,255,.04)', color: isCompleted ? '#56e0b0' : inProgress ? '#feb155' : 'rgba(255,255,255,.4)' }}
                      >
                        {isCompleted ? <CheckCircle2 size={14} /> : <TypeIcon size={14} />}
                      </span>
                      <div className="flex-1 min-w-0">
                        <p className="text-[13.5px] font-semibold text-white m-0 group-hover:text-accent-cyan transition-colors truncate">{scenario.title}</p>
                        <p className="text-[11.5px] text-white/40 mt-0.5">{diff.label} · {scenario.max_score || 100} XP</p>
                      </div>
                      <span className="text-[11px] font-semibold shrink-0" style={{ color: isCompleted ? '#56e0b0' : inProgress ? '#feb155' : 'rgba(255,255,255,.35)' }}>
                        {isCompleted ? 'Done' : inProgress ? 'In progress' : scenario.is_accessible === false ? 'Locked' : 'Start'}
                      </span>
                      {scenario.is_accessible === false && <Lock size={12} className="text-white/30 shrink-0" />}
                    </Link>
                  )
                })}
              </div>
            ) : (
              <div className="py-12 text-center">
                <Target size={32} className="mx-auto text-white/20 mb-3" />
                <p className="text-white/45">No scenarios available yet.</p>
              </div>
            )}

            {/* Full scenario list by difficulty */}
            {hasScenarios && scenarios.length > popularScenarios.length && (
              <div className="mt-6 pt-6 border-t border-white/[0.06]">
                <h4 className="text-sm font-semibold text-white/70 mb-3">All scenarios by difficulty</h4>
                {['easy', 'medium', 'hard'].map(difficulty => {
                  const diffScenarios = scenarios.filter(s => s.difficulty === difficulty)
                  if (!diffScenarios.length) return null
                  const cfg = difficultyConfig[difficulty]
                  return (
                    <div key={difficulty} className="mb-4 last:mb-0">
                      <p className="text-[11px] font-bold uppercase tracking-wider mb-2" style={{ color: cfg.color }}>{cfg.label} ({diffScenarios.length})</p>
                      {diffScenarios.map(scenario => (
                        <Link key={scenario.id} to={`/scenarios/${scenario.slug}`} className="flex items-center gap-2 py-2 text-sm text-white/75 hover:text-accent-cyan transition-colors">
                          <ChevronRight size={12} className="text-white/25" />
                          <span className="truncate">{scenario.title}</span>
                        </Link>
                      ))}
                    </div>
                  )
                })}
              </div>
            )}
          </FxPanel>

          <div className="flex flex-col gap-[22px]">
            <FxPanel padding="p-[22px]">
              <h3 className="font-display font-bold text-[15px] text-white m-0 mb-1.5 flex items-center gap-2">
                <Award size={16} className="text-accent-amber" /> Certification
              </h3>
              {certTracks.length > 0 ? (
                <>
                  <p className="text-[12.5px] text-white/50 m-0 mb-3 leading-relaxed">
                    Vendor certification labs for {tech.name} live in a separate track — not mixed with regular scenarios.
                  </p>
                  <div className="space-y-2">
                    {certTracks.map((ct) => (
                      <Link
                        key={ct.slug}
                        to={`/certifications/${ct.slug}`}
                        className="block text-sm px-3 py-2 rounded-lg border border-amber-500/25 bg-amber-500/5 text-amber-200 hover:bg-amber-500/10 transition-colors"
                      >
                        {ct.name} {ct.exam_code ? <span className="text-white/40 font-mono text-xs">({ct.exam_code})</span> : null}
                      </Link>
                    ))}
                  </div>
                </>
              ) : (
                <>
                  <p className="text-[12.5px] text-white/50 m-0 mb-3.5 leading-relaxed">
                    Complete all {stats?.total || 0} labs to earn the {tech.name} platform certificate.
                  </p>
                  <div className="h-[7px] rounded bg-white/[0.06] overflow-hidden mb-2">
                    <div className="h-full rounded bg-gradient-to-r from-accent-amber to-orange-400" style={{ width: `${progressPct}%` }} />
                  </div>
                  <p className="text-[11.5px] text-white/45 m-0">
                    {(stats?.total || 0) - (stats?.completed || 0)} labs to go
                  </p>
                </>
              )}
            </FxPanel>

            {skills.length > 0 && (
              <FxPanel padding="p-[22px]">
                <h3 className="font-display font-bold text-[15px] text-white m-0 mb-3.5">Skills covered</h3>
                <div className="flex flex-wrap gap-2">
                  {skills.map(skill => (
                    <span key={skill} className="text-xs font-medium px-3 py-1.5 rounded-lg bg-white/[0.04] border border-white/10 text-white/72">
                      {skill}
                    </span>
                  ))}
                </div>
              </FxPanel>
            )}
          </div>
        </div>
      )}

      {activeTab === 'projects' && hasProjects && (
        <div className="space-y-4">
          <FxPanel className="border-accent-purple/25 bg-gradient-to-r from-accent-purple/[0.08] to-accent-cyan/[0.04]">
            <div className="flex items-start gap-3">
              <FolderKanban size={20} className="text-accent-purple shrink-0 mt-0.5" />
              <div>
                <p className="text-sm font-semibold text-white">End-to-End Projects</p>
                <p className="text-xs text-white/50 mt-0.5">
                  Build real architectures step-by-step. Each project is guided by Jira tickets — open them in the AI lab, complete the tasks, and ask the Jira bot if you get stuck.
                </p>
              </div>
            </div>
          </FxPanel>
          {projects.map(project => (
            <ProjectCard key={project.id} project={project} onStart={handleStartProject} />
          ))}
        </div>
      )}
    </motion.div>
  )
}
