import { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { scenarioApi } from '../api/scenarios'
import {
  Server, Cloud, Globe, Monitor, Database, Cpu,
  ArrowRight, Layers, Shield
} from 'lucide-react'
import toast from 'react-hot-toast'
import StickyPageToolbar from '../components/StickyPageToolbar'

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

export default function Technologies() {
  const navigate = useNavigate()
  const [technologies, setTechnologies] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    scenarioApi.getTechnologies()
      .then(setTechnologies)
      .catch(() => toast.error('Failed to load technologies'))
      .finally(() => setLoading(false))
  }, [])

  const openTechnology = (tech) => {
    navigate(`/technologies/${tech.slug}`)
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
      <StickyPageToolbar>
      <div className="relative overflow-hidden glass-card p-6 sm:p-8">
        <div className="absolute inset-0 bg-gradient-to-r from-accent-cyan/8 via-transparent to-accent-purple/8" />
        <div className="absolute inset-0 bg-dots-pattern opacity-20" />
        <div className="relative flex items-center justify-between gap-3">
          <div className="min-w-0">
            <h1 className="text-2xl sm:text-3xl font-black text-white tracking-tight flex items-center gap-3">
              <Layers size={24} className="text-accent-cyan shrink-0" />
              <span className="bg-gradient-to-r from-accent-cyan to-accent-purple bg-clip-text text-transparent truncate">Technologies</span>
            </h1>
            <p className="text-surface-400 mt-2 text-sm">
              Choose a technology to explore its challenges
            </p>
          </div>
          <Link to="/scenarios" className="text-sm text-surface-400 hover:text-accent-cyan transition-colors flex items-center gap-1 shrink-0">
            View All Scenarios <ArrowRight size={14} />
          </Link>
        </div>
      </div>
      </StickyPageToolbar>

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
        {sortedTechnologies.map(tech => {
          const Icon = techIcons[tech.name] || Server
          const colorClass = techColors[tech.color] || techColors.cyan
          if (tech.coming_soon) {
            return (
              <button
                key={tech.id}
                type="button"
                onClick={() => openTechnology(tech)}
                className="relative p-5 rounded-xl border border-dashed border-surface-700/50 bg-surface-900/30 opacity-50 hover:opacity-65 transition-all text-left"
              >
                <Icon size={28} className="mb-3 text-surface-600" />
                <h3 className="text-base font-semibold text-surface-500 mb-1">{tech.name}</h3>
                <span className="text-xs text-accent-amber font-medium">Coming soon</span>
              </button>
            )
          }
          return (
            <button
              key={tech.id}
              type="button"
              onClick={() => openTechnology(tech)}
              className={`relative p-5 rounded-xl border transition-all duration-200 text-left group bg-surface-800/50 border-surface-700/50 hover:border-surface-600 hover:bg-surface-800 hover:scale-[1.02] hover:bg-gradient-to-br ${colorClass}`}
            >
              <Icon size={28} className="mb-3 text-surface-400 group-hover:text-accent-cyan transition-colors" />
              <h3 className="text-base font-semibold text-white mb-1">{tech.name}</h3>
              <span className="text-xs text-surface-500">
                {tech.scenario_count || 0} scenario{tech.scenario_count !== 1 ? 's' : ''}
              </span>
              <ArrowRight size={14} className="absolute top-4 right-4 text-surface-600 group-hover:text-accent-cyan transition-colors" />
            </button>
          )
        })}
      </div>
    </div>
  )
}
