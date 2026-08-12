import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { Clock, FolderKanban, Play } from 'lucide-react'
import toast from 'react-hot-toast'
import PublicLayout from '../../components/layout/PublicLayout'
import { FixitPanel } from '../../components/design'
import { usePageTitle } from '../../hooks/usePageTitle'
import { projectApi } from '../../api/projects'
import { useAuthStore } from '../../store/authStore'
import PageBreadcrumbs from '../../components/PageBreadcrumbs'

export default function ProjectDetail() {
  const { slug } = useParams()
  const navigate = useNavigate()
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)
  const [project, setProject] = useState(null)
  const [loading, setLoading] = useState(true)
  const [starting, setStarting] = useState(false)
  const [error, setError] = useState(false)

  usePageTitle(
    project ? `${project.title} — Capstone Project` : 'Capstone Project',
    project?.description || 'Guided FixitLab capstone project.',
  )

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(false)
    projectApi.get(slug)
      .then((data) => { if (!cancelled) setProject(data) })
      .catch(() => { if (!cancelled) setError(true) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [slug])

  const startProject = async () => {
    if (!isAuthenticated) {
      navigate('/login', { state: { from: `/projects/${slug}` } })
      return
    }
    if (!project?.id || starting) return
    setStarting(true)
    try {
      const started = await projectApi.start(project.id)
      if (started?.lab_scenario_id) {
        try {
          const { labApi } = await import('../../api/labs')
          const session = await labApi.startLab(started.lab_scenario_id)
          toast.success(`Project workspace ready: ${project.title}`)
          navigate(`/lab/${session.id}`, {
            state: { techSlug: project.technology?.slug },
          })
          return
        } catch (e) {
          if (e?.response?.status === 403) {
            toast.error(e.response?.data?.error || 'Subscribe to open this project workspace.')
          } else {
            toast.error('Workspace could not start — opening the technology page instead.')
          }
        }
      }
      toast.success(`Project started: ${project.title}`)
      if (project.technology?.slug) {
        navigate(`/technologies/${project.technology.slug}`)
      }
    } catch {
      toast.error('Could not start project. Please log in.')
    } finally {
      setStarting(false)
    }
  }

  if (loading) {
    return (
      <PublicLayout>
        <div className="max-w-3xl mx-auto px-4 py-16 text-surface-400 text-sm">Loading project…</div>
      </PublicLayout>
    )
  }

  if (error || !project) {
    return (
      <PublicLayout>
        <div className="max-w-3xl mx-auto px-4 py-16">
          <p className="text-surface-300 mb-4">Project not found.</p>
          <Link to="/projects" className="btn-secondary text-sm">All projects</Link>
        </div>
      </PublicLayout>
    )
  }

  const objectives = project.objectives || []
  const tasks = project.tasks || []

  return (
    <PublicLayout>
      <div className="max-w-3xl mx-auto px-4 py-10">
        <PageBreadcrumbs
          className="mb-6"
          items={[
            { label: 'Home', to: '/' },
            { label: 'Projects', to: '/projects' },
            { label: project.title },
          ]}
        />

        <div className="flex items-start gap-4 mb-6">
          <div className="w-12 h-12 rounded-xl bg-surface-800/70 border border-surface-700 flex items-center justify-center text-accent-cyan shrink-0">
            <FolderKanban size={22} />
          </div>
          <div className="min-w-0">
            <p className="text-[11px] font-medium uppercase tracking-wider text-surface-500 mb-1">
              {project.technology?.name || 'Capstone'}
            </p>
            <h1 className="font-display text-2xl font-semibold text-white leading-tight">{project.title}</h1>
            <p className="text-sm text-surface-400 mt-2 flex flex-wrap items-center gap-3">
              <span className="capitalize">{project.difficulty}</span>
              <span className="inline-flex items-center gap-1"><Clock size={13} /> ~{project.estimated_hours || 4}h</span>
              {tasks.length > 0 && <span>{tasks.length} tasks</span>}
            </p>
          </div>
        </div>

        <FixitPanel className="p-5 mb-6">
          <p className="text-surface-300 leading-relaxed whitespace-pre-wrap">{project.description}</p>
          {objectives.length > 0 && (
            <ul className="mt-4 space-y-1.5">
              {objectives.map((obj) => (
                <li key={obj} className="text-sm text-surface-400 flex gap-2">
                  <span className="text-accent-cyan">•</span>
                  <span>{obj}</span>
                </li>
              ))}
            </ul>
          )}
          <div className="mt-5 flex flex-wrap gap-3">
            <button
              type="button"
              onClick={startProject}
              disabled={starting}
              className="btn-primary text-sm inline-flex items-center gap-1.5"
            >
              <Play size={14} />
              {starting ? 'Starting…' : (project.has_lab ? 'Start project lab' : 'Start project')}
            </button>
            {project.technology?.slug && (
              <Link
                to={`/technologies/${project.technology.slug}`}
                className="btn-secondary text-sm"
              >
                View technology
              </Link>
            )}
          </div>
        </FixitPanel>

        {tasks.length > 0 && (
          <FixitPanel className="p-5">
            <h2 className="text-sm font-semibold text-white mb-3">Tasks</h2>
            <ol className="space-y-2">
              {tasks.map((t) => (
                <li key={t.id} className="text-sm text-surface-300 flex gap-2">
                  <span className="text-surface-500 shrink-0 font-mono text-xs mt-0.5">{t.jira_key}</span>
                  <span>{t.title}</span>
                </li>
              ))}
            </ol>
          </FixitPanel>
        )}
      </div>
    </PublicLayout>
  )
}
