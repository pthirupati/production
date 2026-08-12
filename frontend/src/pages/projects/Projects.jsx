import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { FolderKanban, ArrowRight, Clock } from 'lucide-react'
import PublicLayout from '../../components/layout/PublicLayout'
import MarketingPageShell from '../../components/MarketingPageShell'
import { usePageTitle } from '../../hooks/usePageTitle'
import { projectApi } from '../../api/projects'

const DIFFICULTY_BADGE = {
  beginner: 'text-accent-green bg-accent-green/10 border-accent-green/20',
  intermediate: 'text-accent-cyan bg-accent-cyan/10 border-accent-cyan/20',
  advanced: 'text-accent-amber bg-accent-amber/10 border-accent-amber/20',
}

function ProjectCard({ project }) {
  const diffCls = DIFFICULTY_BADGE[project.difficulty] || DIFFICULTY_BADGE.intermediate
  return (
    <Link
      to={`/projects/${project.slug}`}
      className="group fx-panel p-5 flex flex-col hover:border-accent-cyan/40 transition-colors"
    >
      <div className="flex items-start justify-between gap-2 mb-3">
        <div className="w-10 h-10 rounded-lg bg-surface-800/70 border border-surface-700 flex items-center justify-center text-accent-cyan group-hover:border-accent-cyan/40 transition-colors">
          <FolderKanban size={20} />
        </div>
        <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full border capitalize ${diffCls}`}>
          {project.difficulty}
        </span>
      </div>
      <p className="text-[11px] font-medium uppercase tracking-wider text-surface-500 mb-1">
        {project.technology?.name || 'Project'}
      </p>
      <h3 className="font-display font-semibold text-white text-base leading-snug mb-1.5 group-hover:text-accent-cyan transition-colors">
        {project.title}
      </h3>
      <p className="text-sm text-surface-400 leading-relaxed flex-1 line-clamp-3">{project.description}</p>
      <div className="mt-4 flex items-center justify-between text-xs text-surface-500">
        <span className="inline-flex items-center gap-1">
          <Clock size={12} />
          ~{project.estimated_hours || 4}h
          {project.task_count ? ` · ${project.task_count} tasks` : ''}
        </span>
        <span className="inline-flex items-center gap-1 font-medium text-accent-cyan">
          Open
          <ArrowRight size={12} className="opacity-0 group-hover:opacity-100 group-hover:translate-x-0.5 transition-all" />
        </span>
      </div>
    </Link>
  )
}

export default function Projects() {
  const [projects, setProjects] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)

  usePageTitle(
    'Capstone Projects',
    'End-to-end guided projects with Jira-style tasks — build real architectures across the FixitLab technology catalog.',
  )

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    projectApi.list()
      .then((data) => { if (!cancelled) setProjects(data?.projects || []) })
      .catch(() => { if (!cancelled) setError(true) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [])

  const byTech = useMemo(() => {
    const groups = {}
    for (const p of projects) {
      const key = p.technology?.name || 'Other'
      ;(groups[key] ||= []).push(p)
    }
    return Object.entries(groups).sort(([a], [b]) => a.localeCompare(b))
  }, [projects])

  return (
    <PublicLayout>
      <MarketingPageShell
        eyebrow="Build end-to-end"
        title="Capstone Projects"
        subtitle="Guided multi-ticket projects that launch a real lab workspace — the missing middle between single scenarios and certifications."
      >
        {loading ? (
          <p className="text-surface-400 text-sm">Loading projects…</p>
        ) : error ? (
          <p className="text-surface-300 mb-1">Couldn&apos;t load projects.</p>
        ) : projects.length === 0 ? (
          <p className="text-surface-300 mb-1">No projects are published yet.</p>
        ) : (
          <div className="space-y-10">
            {byTech.map(([tech, items]) => (
              <section key={tech}>
                <h2 className="text-sm font-semibold text-surface-300 uppercase tracking-wider mb-4">{tech}</h2>
                <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
                  {items.map((p) => <ProjectCard key={p.slug} project={p} />)}
                </div>
              </section>
            ))}
          </div>
        )}
      </MarketingPageShell>
    </PublicLayout>
  )
}
