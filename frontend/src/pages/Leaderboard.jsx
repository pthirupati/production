import { useState, useEffect } from 'react'
import { labApi } from '../api/labs'
import { useAuthStore } from '../store/authStore'
import { useDataStore } from '../store/dataStore'
import { Trophy, Medal, Crown, Star, Clock, TrendingUp } from 'lucide-react'
import Pagination from '../components/Pagination'
import StickyPageToolbar from '../components/StickyPageToolbar'

const PAGE_SIZE = 20

export default function Leaderboard() {
  const { user } = useAuthStore()
  const getTechnologies = useDataStore(s => s.getTechnologies)
  const [data, setData] = useState({ leaderboard: [], user_rank: null })
  const [technologies, setTechnologies] = useState([])
  const [selectedTech, setSelectedTech] = useState('')
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(1)

  useEffect(() => {
    getTechnologies().then(techs => setTechnologies(techs)).catch(console.error)
  }, [])

  useEffect(() => {
    setLoading(true)
    labApi.getLeaderboard(selectedTech || undefined)
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [selectedTech])

  const getRankDisplay = (rank) => {
    if (rank === 1) return (
      <div className="w-8 h-8 rounded-full bg-yellow-400/10 flex items-center justify-center">
        <Crown size={16} className="text-yellow-400" />
      </div>
    )
    if (rank === 2) return (
      <div className="w-8 h-8 rounded-full bg-gray-300/10 flex items-center justify-center">
        <Medal size={16} className="text-gray-300" />
      </div>
    )
    if (rank === 3) return (
      <div className="w-8 h-8 rounded-full bg-amber-600/10 flex items-center justify-center">
        <Medal size={16} className="text-amber-600" />
      </div>
    )
    return <span className="w-8 h-8 flex items-center justify-center text-sm text-surface-500 font-mono">{rank}</span>
  }

  const formatTime = (seconds) => {
    if (!seconds) return '—'
    const m = Math.floor(seconds / 60)
    const s = Math.round(seconds % 60)
    return `${m}m ${s}s`
  }

  return (
    <div className="max-w-5xl mx-auto space-y-6 animate-fade-in">
      <StickyPageToolbar>
      <div className="relative overflow-hidden glass-card p-6 sm:p-8">
        <div className="absolute inset-0 bg-gradient-to-r from-accent-amber/8 via-transparent to-accent-cyan/8" />
        <div className="absolute inset-0 bg-dots-pattern opacity-20" />
        <div className="relative">
          <h1 className="text-2xl sm:text-3xl font-black text-white tracking-tight flex items-center gap-3">
            <Trophy className="text-accent-amber shrink-0" /> <span className="bg-gradient-to-r from-accent-amber to-accent-cyan bg-clip-text text-transparent">Leaderboard</span>
          </h1>
          <p className="text-surface-400 mt-2 text-sm">Top fixers ranked by total score</p>
        </div>
      </div>

      {/* Tech filter */}
      <div className="flex gap-2 flex-wrap">
        <button onClick={() => setSelectedTech('')}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
            !selectedTech ? 'bg-accent-cyan/10 text-accent-cyan border border-accent-cyan/20' : 'text-surface-400 hover:text-white bg-surface-800 border border-surface-700'
          }`}>
          Global
        </button>
        {technologies.map((tech) => (
          <button key={tech.id}
            onClick={() => setSelectedTech(selectedTech === String(tech.id) ? '' : String(tech.id))}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              selectedTech === String(tech.id) ? 'bg-accent-cyan/10 text-accent-cyan border border-accent-cyan/20' : 'text-surface-400 hover:text-white bg-surface-800 border border-surface-700'
            }`}>
            {tech.name}
          </button>
        ))}
      </div>
      </StickyPageToolbar>

      {/* Your rank */}
      {data.user_rank && (
        <div className="glass-card p-4 border-accent-cyan/20 bg-accent-cyan/5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 rounded-xl bg-accent-cyan/10 flex items-center justify-center">
                <Star size={22} className="text-accent-cyan" />
              </div>
              <div>
                <p className="text-xs text-surface-400 uppercase tracking-wider">Your Rank</p>
                <p className="text-2xl font-bold text-white">#{data.user_rank.rank}</p>
              </div>
            </div>
            <div className="flex items-center gap-6">
              <div className="text-right">
                <p className="text-xl font-bold text-accent-amber">{data.user_rank.total_score}</p>
                <p className="text-xs text-surface-500">Total Score</p>
              </div>
              <div className="text-right">
                <p className="text-lg font-bold text-surface-300">{data.user_rank.scenarios_completed || 0}</p>
                <p className="text-xs text-surface-500">Solved</p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Leaderboard table */}
      <div className="glass-card overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center h-40">
            <div className="w-8 h-8 border-2 border-accent-cyan border-t-transparent rounded-full animate-spin" />
          </div>
        ) : data.leaderboard.length === 0 ? (
          <div className="text-center py-16">
            <Trophy size={40} className="text-surface-700 mx-auto mb-3" />
            <p className="text-surface-500">No entries yet. Be the first!</p>
          </div>
        ) : (
          <>
          <div className="overflow-x-auto">
          <table className="w-full min-w-[480px]">
            <thead>
              <tr className="border-b border-surface-700/50 text-left">
                <th className="px-4 sm:px-6 py-3 text-xs font-medium text-surface-400 uppercase w-16">Rank</th>
                <th className="px-4 sm:px-6 py-3 text-xs font-medium text-surface-400 uppercase">Player</th>
                <th className="px-4 sm:px-6 py-3 text-xs font-medium text-surface-400 uppercase text-right">Solved</th>
                <th className="px-4 sm:px-6 py-3 text-xs font-medium text-surface-400 uppercase text-right hidden sm:table-cell">Avg Time</th>
                <th className="px-4 sm:px-6 py-3 text-xs font-medium text-surface-400 uppercase text-right">Score</th>
              </tr>
            </thead>
            <tbody>
              {data.leaderboard.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE).map((entry, i) => {
                const isUser = entry.username === user?.username
                const actualIndex = (page - 1) * PAGE_SIZE + i
                return (
                  <tr key={entry.rank}
                    className={`border-b border-surface-800/50 transition-colors ${
                      isUser ? 'bg-accent-cyan/5 hover:bg-accent-cyan/10' : 'hover:bg-surface-800/30'
                    } ${actualIndex < 3 ? 'bg-surface-800/20' : ''}`}>
                    <td className="px-4 sm:px-6 py-3">{getRankDisplay(entry.rank)}</td>
                    <td className="px-4 sm:px-6 py-3">
                      <span className={`font-medium ${isUser ? 'text-accent-cyan' : 'text-white'}`}>
                        {entry.username}
                        {isUser && <span className="text-xs text-accent-cyan/60 ml-2">(you)</span>}
                      </span>
                    </td>
                    <td className="px-4 sm:px-6 py-3 text-right text-surface-400">{entry.scenarios_completed}</td>
                    <td className="px-4 sm:px-6 py-3 text-right hidden sm:table-cell">
                      <span className="text-surface-500 text-sm flex items-center justify-end gap-1">
                        <Clock size={12} /> {formatTime(entry.avg_time)}
                      </span>
                    </td>
                    <td className="px-4 sm:px-6 py-3 text-right">
                      <span className={`font-mono font-bold ${actualIndex === 0 ? 'text-yellow-400 text-lg' : actualIndex < 3 ? 'text-accent-amber' : 'text-accent-amber/80'}`}>
                        {entry.total_score}
                      </span>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
          </div>
          {data.leaderboard.length > PAGE_SIZE && (
            <Pagination
              currentPage={page}
              totalPages={Math.ceil(data.leaderboard.length / PAGE_SIZE)}
              onPageChange={(p) => { setPage(p); window.scrollTo({ top: 0, behavior: 'smooth' }) }}
            />
          )}
          </>
        )}
      </div>
    </div>
  )
}
