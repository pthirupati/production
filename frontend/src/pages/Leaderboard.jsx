import { useState, useEffect } from 'react'
import { labApi } from '../api/labs'
import { useAuthStore } from '../store/authStore'
import { useDataStore } from '../store/dataStore'
import { Trophy, Star, Clock, Crown, Medal, Server } from 'lucide-react'
import Pagination from '../components/Pagination'
import CompactPageHeader from '../components/CompactPageHeader'
import { SkeletonTable } from '../components/Skeleton'

const PAGE_SIZE = 20

// ── Helpers ──────────────────────────────────────────────────────────────────

function formatTime(seconds) {
  if (!seconds) return '—'
  const m = Math.floor(seconds / 60)
  const s = Math.round(seconds % 60)
  return `${m}m ${s}s`
}

// ── Podium card for ranks 1–3 ────────────────────────────────────────────────

const podiumConfig = {
  1: {
    icon: Crown,
    iconColor: 'text-yellow-400',
    ringCls: 'ring-2 ring-yellow-400/30',
    bgCls: 'bg-yellow-400/5',
    borderCls: 'border-yellow-400/20',
    labelColor: 'text-yellow-400',
    scoreColor: 'text-yellow-400',
    label: '1st',
  },
  2: {
    icon: Medal,
    iconColor: 'text-slate-300',
    ringCls: '',
    bgCls: 'bg-slate-300/5',
    borderCls: 'border-slate-300/20',
    labelColor: 'text-slate-300',
    scoreColor: 'text-slate-300',
    label: '2nd',
  },
  3: {
    icon: Medal,
    iconColor: 'text-amber-600',
    ringCls: '',
    bgCls: 'bg-amber-600/5',
    borderCls: 'border-amber-600/20',
    labelColor: 'text-amber-600',
    scoreColor: 'text-amber-600',
    label: '3rd',
  },
}

function PodiumCard({ entry, currentUsername }) {
  const cfg = podiumConfig[entry.rank]
  const Icon = cfg.icon
  const isUser = entry.username === currentUsername
  const isFirst = entry.rank === 1

  return (
    <div
      className={`
        relative flex-1 min-w-0 rounded-xl border p-4 sm:p-5
        glass-card transition-all duration-300
        ${cfg.borderCls} ${cfg.bgCls} ${cfg.ringCls}
        ${isFirst ? 'sm:-translate-y-2' : ''}
        ${isUser ? 'ring-1 ring-accent-cyan/40' : ''}
        animate-slide-up
      `}
      style={{ animationDelay: `${(entry.rank - 1) * 80}ms` }}
    >
      {/* Rank label + icon */}
      <div className="flex items-center justify-between mb-4">
        <span className={`text-[11px] font-bold uppercase tracking-widest ${cfg.labelColor}`}>
          {cfg.label}
        </span>
        <div className={`w-8 h-8 rounded-full ${cfg.bgCls} border ${cfg.borderCls} flex items-center justify-center`}>
          <Icon size={isFirst ? 17 : 15} className={cfg.iconColor} />
        </div>
      </div>

      {/* Avatar */}
      <div className={`w-12 h-12 rounded-xl flex items-center justify-center mb-3 font-black text-xl border ${cfg.borderCls} ${cfg.bgCls} ${cfg.iconColor}`}>
        {entry.username?.slice(0, 1).toUpperCase() || '?'}
      </div>

      {/* Name */}
      <p className={`font-bold truncate ${isFirst ? 'text-base' : 'text-sm'} ${isUser ? 'text-accent-cyan' : 'text-white'}`}>
        {entry.username}
        {isUser && <span className="ml-1 text-[10px] font-normal text-accent-cyan/60">(you)</span>}
      </p>

      {/* Score */}
      <p className={`font-black font-mono mt-1 ${isFirst ? 'text-2xl' : 'text-xl'} ${cfg.scoreColor}`}>
        {entry.total_score?.toLocaleString()}
      </p>

      {/* Stats footer */}
      <div className="flex items-center gap-3 mt-3 pt-3 border-t border-surface-800/60 flex-wrap">
        <span className="text-[11px] text-surface-400 flex items-center gap-1">
          <Trophy size={10} className="text-surface-500 shrink-0" />
          {entry.scenarios_completed ?? 0} solved
        </span>
        {entry.avg_time > 0 && (
          <span className="text-[11px] text-surface-500 flex items-center gap-1">
            <Clock size={10} className="shrink-0" />
            {formatTime(entry.avg_time)}
          </span>
        )}
      </div>
    </div>
  )
}

// ── Rank cell for table ───────────────────────────────────────────────────────

function RankCell({ rank }) {
  if (rank === 1) return (
    <div className="w-8 h-8 rounded-full bg-yellow-400/10 flex items-center justify-center">
      <Crown size={14} className="text-yellow-400" />
    </div>
  )
  if (rank === 2) return (
    <div className="w-8 h-8 rounded-full bg-slate-300/10 flex items-center justify-center">
      <Medal size={14} className="text-slate-300" />
    </div>
  )
  if (rank === 3) return (
    <div className="w-8 h-8 rounded-full bg-amber-600/10 flex items-center justify-center">
      <Medal size={14} className="text-amber-600" />
    </div>
  )
  return (
    <span className="w-8 h-8 flex items-center justify-center text-sm text-surface-500 font-mono tabular-nums">
      {rank}
    </span>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function Leaderboard() {
  const { user } = useAuthStore()
  const getTechnologies = useDataStore(s => s.getTechnologies)
  const [data, setData] = useState({ leaderboard: [], user_rank: null })
  const [technologies, setTechnologies] = useState([])
  const [selectedTech, setSelectedTech] = useState('')
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(1)

  useEffect(() => {
    getTechnologies().then(setTechnologies).catch(console.error)
  }, [])

  useEffect(() => {
    setLoading(true)
    setPage(1)
    labApi.getLeaderboard(selectedTech || undefined)
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [selectedTech])

  const leaderboard = data.leaderboard || []
  const top3 = leaderboard.slice(0, 3)
  const tableRows = leaderboard.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)

  return (
    <div className="max-w-5xl mx-auto space-y-6 animate-fade-in">

      <CompactPageHeader
        title="Leaderboard"
        subtitle="Top fixers ranked by total score"
        eyebrow="Rankings"
        icon={Trophy}
      />

      {/* Tech filter chips */}
      <div className="flex gap-2 flex-wrap">
        <button
          onClick={() => setSelectedTech('')}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all ${
            !selectedTech
              ? 'bg-accent-cyan/10 text-accent-cyan border-accent-cyan/20'
              : 'bg-surface-800 text-surface-400 hover:text-white border-surface-700'
          }`}
        >
          <Trophy size={11} /> Global
        </button>
        {technologies.map(tech => (
          <button
            key={tech.id}
            onClick={() => setSelectedTech(selectedTech === String(tech.id) ? '' : String(tech.id))}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all ${
              selectedTech === String(tech.id)
                ? 'bg-accent-cyan/10 text-accent-cyan border-accent-cyan/20'
                : 'bg-surface-800 text-surface-400 hover:text-white border-surface-700'
            }`}
          >
            <Server size={11} />
            {tech.name}
          </button>
        ))}
      </div>

      {/* ── Your rank banner (only if outside top 3) ── */}
      {!loading && data.user_rank && data.user_rank.rank > 3 && (
        <div className="glass-card p-4 border border-accent-cyan/20 bg-accent-cyan/5 animate-fade-in">
          <div className="flex items-center justify-between gap-4 flex-wrap">
            <div className="flex items-center gap-4">
              <div className="w-11 h-11 rounded-xl bg-accent-cyan/10 border border-accent-cyan/20 flex items-center justify-center">
                <Star size={20} className="text-accent-cyan" />
              </div>
              <div>
                <p className="text-[10px] text-surface-500 uppercase tracking-widest font-semibold">Your Rank</p>
                <p className="text-2xl font-black text-white leading-none">#{data.user_rank.rank}</p>
              </div>
            </div>
            <div className="flex items-center gap-6">
              <div className="text-right">
                <p className="text-xl font-black text-accent-amber font-mono">
                  {data.user_rank.total_score?.toLocaleString()}
                </p>
                <p className="text-[10px] text-surface-500 uppercase tracking-wider">Total Score</p>
              </div>
              <div className="text-right">
                <p className="text-lg font-bold text-surface-300">
                  {data.user_rank.scenarios_completed ?? 0}
                </p>
                <p className="text-[10px] text-surface-500 uppercase tracking-wider">Solved</p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── Main content ── */}
      {loading ? (
        <div className="space-y-4 animate-fade-in">
          {/* Podium skeleton */}
          <div className="grid grid-cols-3 gap-3 sm:gap-4">
            {[1, 2, 3].map(i => (
              <div key={i} className="glass-card p-5 space-y-3 animate-pulse">
                <div className="flex justify-between">
                  <div className="h-3 w-8 bg-surface-800 rounded" />
                  <div className="w-8 h-8 bg-surface-800 rounded-full" />
                </div>
                <div className="w-12 h-12 bg-surface-800 rounded-xl" />
                <div className="h-4 w-24 bg-surface-800 rounded" />
                <div className="h-6 w-16 bg-surface-800 rounded" />
              </div>
            ))}
          </div>
          <SkeletonTable rows={8} cols={5} />
        </div>
      ) : leaderboard.length === 0 ? (
        <div className="glass-card p-16 text-center animate-fade-in">
          <Trophy size={44} className="text-surface-700 mx-auto mb-4" />
          <p className="text-white font-bold text-lg mb-1">No entries yet</p>
          <p className="text-surface-500 text-sm">Be the first to claim the top spot!</p>
        </div>
      ) : (
        <div className="space-y-6 animate-fade-in">

          {/* ── Top 3 podium: 2nd | 1st | 3rd ── */}
          {top3.length > 0 && (
            <div>
              <p className="text-[11px] font-semibold text-surface-500 uppercase tracking-widest mb-3 px-1">
                Top Performers
              </p>
              <div className="flex gap-3 sm:gap-4 items-end">
                {[
                  top3.find(e => e.rank === 2),
                  top3.find(e => e.rank === 1),
                  top3.find(e => e.rank === 3),
                ].filter(Boolean).map(entry => (
                  <PodiumCard
                    key={entry.rank}
                    entry={entry}
                    currentUsername={user?.username}
                  />
                ))}
              </div>
            </div>
          )}

          {/* ── Rankings table ── */}
          <div>
            <p className="text-[11px] font-semibold text-surface-500 uppercase tracking-widest mb-3 px-1">
              Rankings
            </p>
            <div className="glass-card overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full min-w-[500px]">
                  <thead>
                    <tr className="border-b border-surface-700/50 text-left">
                      <th className="px-4 sm:px-5 py-3 text-[11px] font-semibold text-surface-500 uppercase tracking-wider w-16">
                        Rank
                      </th>
                      <th className="px-4 sm:px-5 py-3 text-[11px] font-semibold text-surface-500 uppercase tracking-wider">
                        Player
                      </th>
                      <th className="px-4 sm:px-5 py-3 text-[11px] font-semibold text-surface-500 uppercase tracking-wider text-right">
                        Solved
                      </th>
                      <th className="px-4 sm:px-5 py-3 text-[11px] font-semibold text-surface-500 uppercase tracking-wider text-right hidden sm:table-cell">
                        Avg Time
                      </th>
                      <th className="px-4 sm:px-5 py-3 text-[11px] font-semibold text-surface-500 uppercase tracking-wider text-right">
                        Score
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {tableRows.map((entry, i) => {
                      const isUser = entry.username === user?.username
                      const isTopThree = entry.rank <= 3

                      return (
                        <tr
                          key={entry.rank}
                          className={`
                            border-b border-surface-800/40 transition-colors
                            ${isUser
                              ? 'bg-accent-cyan/5 hover:bg-accent-cyan/10'
                              : i % 2 === 0
                                ? 'bg-surface-900/30 hover:bg-surface-800/30'
                                : 'hover:bg-surface-800/20'
                            }
                          `}
                        >
                          <td className="px-4 sm:px-5 py-3">
                            <RankCell rank={entry.rank} />
                          </td>
                          <td className="px-4 sm:px-5 py-3">
                            <div className="flex items-center gap-2">
                              <div className={`
                                w-7 h-7 rounded-lg flex items-center justify-center text-[11px] font-bold shrink-0
                                ${isUser ? 'bg-accent-cyan/15 text-accent-cyan' : 'bg-surface-800 text-surface-400'}
                              `}>
                                {entry.username?.slice(0, 1).toUpperCase() || '?'}
                              </div>
                              <span className={`font-semibold text-sm ${isUser ? 'text-accent-cyan' : 'text-white'}`}>
                                {entry.username}
                              </span>
                              {isUser && (
                                <span className="text-[10px] text-accent-cyan/60">(you)</span>
                              )}
                            </div>
                          </td>
                          <td className="px-4 sm:px-5 py-3 text-right">
                            <span className="text-sm text-surface-300 font-medium">
                              {entry.scenarios_completed ?? 0}
                            </span>
                          </td>
                          <td className="px-4 sm:px-5 py-3 text-right hidden sm:table-cell">
                            <span className="text-sm text-surface-500 flex items-center justify-end gap-1">
                              <Clock size={11} className="shrink-0" />
                              {formatTime(entry.avg_time)}
                            </span>
                          </td>
                          <td className="px-4 sm:px-5 py-3 text-right">
                            <span className={`
                              font-mono font-black tabular-nums
                              ${entry.rank === 1 ? 'text-yellow-400 text-base' : ''}
                              ${entry.rank === 2 ? 'text-slate-300 text-sm' : ''}
                              ${entry.rank === 3 ? 'text-amber-600 text-sm' : ''}
                              ${entry.rank > 3 ? 'text-accent-amber/80 text-sm' : ''}
                            `}>
                              {entry.total_score?.toLocaleString()}
                            </span>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>

              {leaderboard.length > PAGE_SIZE && (
                <div className="border-t border-surface-800/50">
                  <Pagination
                    currentPage={page}
                    totalPages={Math.ceil(leaderboard.length / PAGE_SIZE)}
                    onPageChange={p => { setPage(p); window.scrollTo({ top: 0, behavior: 'smooth' }) }}
                  />
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
