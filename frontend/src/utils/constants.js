import {
  Star, Zap, Target, Trophy, Flame, Award, CheckCircle2,
} from 'lucide-react'

/**
 * Shared achievement metadata — single source of truth.
 * Used by Dashboard (icon, color, label) and Achievements (+ bg, border, desc).
 */
export const ACHIEVEMENT_META = {
  first_solve:    { icon: Star,         color: 'text-yellow-400',  bg: 'bg-yellow-400/10',  border: 'border-yellow-400/20',  label: 'First Solve',     desc: 'Solve your very first scenario' },
  speed_demon:    { icon: Zap,          color: 'text-cyan-400',    bg: 'bg-cyan-400/10',    border: 'border-cyan-400/20',    label: 'Speed Demon',     desc: 'Solve a scenario in under 25% of the time limit' },
  no_hints:       { icon: Target,       color: 'text-green-400',   bg: 'bg-green-400/10',   border: 'border-green-400/20',   label: 'No Hints',        desc: 'Complete a scenario without using any hints' },
  perfect_score:  { icon: Trophy,       color: 'text-amber-400',   bg: 'bg-amber-400/10',   border: 'border-amber-400/20',   label: 'Perfect Score',   desc: 'Achieve a perfect score of 190+' },
  streak_3:       { icon: Flame,        color: 'text-orange-400',  bg: 'bg-orange-400/10',  border: 'border-orange-400/20',  label: '3-Day Streak',    desc: 'Solve scenarios 3 days in a row' },
  streak_7:       { icon: Flame,        color: 'text-orange-500',  bg: 'bg-orange-500/10',  border: 'border-orange-500/20',  label: '7-Day Streak',    desc: 'Maintain a 7-day solving streak' },
  streak_30:      { icon: Flame,        color: 'text-red-500',     bg: 'bg-red-500/10',     border: 'border-red-500/20',     label: '30-Day Streak',   desc: 'Incredible! 30-day solving streak' },
  easy_master:    { icon: Award,        color: 'text-green-400',   bg: 'bg-green-400/10',   border: 'border-green-400/20',   label: 'Easy Master',     desc: 'Complete all Easy scenarios' },
  medium_master:  { icon: Award,        color: 'text-amber-400',   bg: 'bg-amber-400/10',   border: 'border-amber-400/20',   label: 'Medium Master',   desc: 'Complete all Medium scenarios' },
  hard_master:    { icon: Award,        color: 'text-red-400',     bg: 'bg-red-400/10',     border: 'border-red-400/20',     label: 'Hard Master',     desc: 'Complete all Hard scenarios' },
  ten_solves:     { icon: CheckCircle2, color: 'text-cyan-400',    bg: 'bg-cyan-400/10',    border: 'border-cyan-400/20',    label: '10 Solves',       desc: 'Solve 10 scenarios' },
  fifty_solves:   { icon: CheckCircle2, color: 'text-purple-400',  bg: 'bg-purple-400/10',  border: 'border-purple-400/20',  label: '50 Solves',       desc: 'Solve 50 scenarios' },
  hundred_solves: { icon: CheckCircle2, color: 'text-amber-400',   bg: 'bg-amber-400/10',   border: 'border-amber-400/20',   label: '100 Solves',      desc: 'Solve 100 scenarios — legendary!' },
}

/**
 * Shared time formatting utilities
 */
export function timeAgo(dateStr) {
  const d = new Date(dateStr)
  const now = new Date()
  const seconds = Math.floor((now - d) / 1000)
  if (seconds < 60) return 'just now'
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`
  if (seconds < 2592000) return `${Math.floor(seconds / 86400)}d ago`
  return d.toLocaleDateString()
}

export function formatDuration(seconds) {
  if (!seconds) return '—'
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m}:${String(s).padStart(2, '0')}`
}
