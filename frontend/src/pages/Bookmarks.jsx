import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { scenarioApi } from '../api/scenarios'
import {
  Bookmark, BookmarkX, Clock, Wrench, Play, Skull,
  Server, ArrowRight, Loader2
} from 'lucide-react'
import toast from 'react-hot-toast'
import { PageHeader, FixitPanel } from '../components/design'

const typeConfig = {
  fix:  { icon: Wrench, label: 'Fix', color: 'text-accent-cyan' },
  do:   { icon: Play,   label: 'Do',  color: 'text-accent-green' },
  hack: { icon: Skull,  label: 'Hack', color: 'text-accent-red' },
}

// 'expert' has no badge-* utility in index.css (only easy/medium/hard exist), so
// it composes the same chip inline from purple accents. The final fallback keeps
// an unknown difficulty legible instead of rendering a colourless chip.
const diffConfig = {
  easy:   'badge-easy',
  medium: 'badge-medium',
  hard:   'badge-hard',
  expert: 'bg-accent-purple/10 text-accent-purple border border-accent-purple/20',
}
const DIFF_FALLBACK = 'bg-surface-800 text-surface-300 border border-surface-700'

export default function Bookmarks() {
  const [bookmarks, setBookmarks] = useState([])
  const [loading, setLoading] = useState(true)

  const fetchBookmarks = async () => {
    try {
      const data = await scenarioApi.getBookmarks()
      setBookmarks(data)
    } catch {
      toast.error('Failed to load bookmarks')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchBookmarks() }, [])

  const handleRemove = async (scenarioId) => {
    try {
      await scenarioApi.toggleBookmark(scenarioId)
      setBookmarks(prev => prev.filter(b => b.id !== scenarioId))
      toast.success('Bookmark removed')
    } catch {
      toast.error('Failed to remove bookmark')
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 animate-spin text-accent-cyan" />
      </div>
    )
  }

  return (
    <div className="max-w-5xl mx-auto space-y-6 animate-fade-in">
      <PageHeader
        eyebrow="Your library"
        title="Bookmarked Scenarios"
        subtitle={`${bookmarks.length} saved scenario${bookmarks.length !== 1 ? 's' : ''}`}
      />

      {bookmarks.length === 0 ? (
        <div className="glass-card p-12 text-center">
          <Bookmark className="w-12 h-12 text-surface-500 mx-auto mb-4" />
          <h2 className="text-xl font-semibold text-surface-200 mb-2">No bookmarks yet</h2>
          <p className="text-surface-400 mb-6">Browse scenarios and bookmark the ones you want to tackle later.</p>
          <Link to="/scenarios" className="btn-primary inline-flex items-center gap-2">
            Browse Scenarios <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
      ) : (
        <FixitPanel padding="p-5" className="grid gap-4">
          {bookmarks.map(scenario => {
            const TypeIcon = typeConfig[scenario.scenario_type]?.icon || Server
            return (
              <div key={scenario.id} className="glass-card p-5 flex items-center justify-between gap-4 hover:border-accent-cyan/30 transition-colors">
                <Link to={`/scenarios/${scenario.slug}`} className="flex-1 min-w-0 flex items-center gap-4">
                  <div className={`p-2 rounded-lg bg-surface-800 ${typeConfig[scenario.scenario_type]?.color || 'text-surface-400'}`}>
                    <TypeIcon className="w-5 h-5" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <h3 className="text-white font-medium truncate">{scenario.title}</h3>
                    {scenario.subtitle && (
                      <p className="text-surface-400 text-sm truncate">{scenario.subtitle}</p>
                    )}
                    <div className="flex items-center gap-3 mt-1.5">
                      <span className={`badge text-xs ${diffConfig[scenario.difficulty] || DIFF_FALLBACK}`}>
                        {scenario.difficulty}
                      </span>
                      <span className="text-xs text-surface-500 flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        {Math.floor((scenario.time_limit || 900) / 60)}m
                      </span>
                      {scenario.technology && (
                        <span className="text-xs text-surface-500">{scenario.technology.name}</span>
                      )}
                    </div>
                  </div>
                </Link>
                <div className="flex items-center gap-2">
                  <Link to={`/scenarios/${scenario.slug}`}
                    className="btn-primary text-sm py-1.5 px-4 flex items-center gap-1.5">
                    <ArrowRight className="w-4 h-4" /> View
                  </Link>
                  <button onClick={() => handleRemove(scenario.id)}
                    className="p-2 text-surface-400 hover:text-accent-red transition-colors"
                    title="Remove bookmark">
                    <BookmarkX className="w-5 h-5" />
                  </button>
                </div>
              </div>
            )
          })}
        </FixitPanel>
      )}
    </div>
  )
}
