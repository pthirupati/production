import { useState, useEffect, useMemo } from 'react'
import { Link } from 'react-router-dom'
import api from '../api/client'
import { Sparkles } from 'lucide-react'
import MarketingPageShell from '../components/MarketingPageShell'
import { FixitPanel } from '../components/design'

const TAG_META = {
  New: { color: 'text-accent-green', bg: 'bg-accent-green/14', border: 'border-accent-green/30', dot: '#56e0b0' },
  Improved: { color: 'text-accent-blue', bg: 'bg-accent-blue/14', border: 'border-accent-blue/30', dot: '#49b5ff' },
  Fixed: { color: 'text-accent-amber', bg: 'bg-accent-amber/14', border: 'border-accent-amber/30', dot: '#feb155' },
}

const DOT_COLORS = ['#56e0b0', '#b266e0', '#49b5ff', '#56e0b0', '#49b5ff']

const FALLBACK_RELEASES = [
  {
    version: 'v2.4',
    tag: 'New',
    date: 'June 2026',
    title: 'Teams, coupons & security',
    dotColor: '#56e0b0',
    items: [
      'Enterprise seat licensing with org invites and per-member analytics',
      'Coupon codes at checkout for technology and interview plans',
      'Admin security dashboards, audit logs, and rate limiting',
      'Community threads now support screenshot attachments',
    ],
  },
  {
    version: 'v2.3',
    tag: 'New',
    date: 'May 2026',
    title: 'AI Interview Studio',
    dotColor: '#b266e0',
    items: [
      'Multi-round voice interviews (technical, manager, HR, leadership)',
      'Resume-aware questions with adaptive STAR scoring and reports',
      'FIXIT-INT certificates with public verification',
      'Pro and Premium interview plans, separate from lab subscriptions',
    ],
  },
  {
    version: 'v2.2',
    tag: 'New',
    date: 'April 2026',
    title: 'Jira incident workflow',
    dotColor: '#56e0b0',
    items: [
      'Personal Jira ticket per learner per scenario with status timeline',
      'Bot account creates and transitions issues via the Jira REST API',
      'Bidirectional webhook sync of status and comments',
      'Built-in AI-powered mode when Jira is not configured',
    ],
  },
  {
    version: 'v2.1',
    tag: 'Improved',
    date: 'March 2026',
    title: 'Cloud labs & faster spin-up',
    dotColor: '#49b5ff',
    items: [
      'AWS EC2 and DigitalOcean lab modes for cloud-native scenarios',
      'Instant AI-powered RHEL environments — ready in seconds',
      'Dual-pane terminals and SSH-client scenarios for networking',
      'Per-scenario blocked-command guardrails and session recording',
    ],
  },
  {
    version: 'v2.0',
    tag: 'New',
    date: 'February 2026',
    title: 'Browser terminal labs',
    dotColor: '#56e0b0',
    items: [
      'Full xterm.js shell over WebSocket — real commands in any browser',
      'Auto-validation checks your fix inside the environment',
      'Global and per-technology leaderboards with timed scoring',
      'Bookmarks, achievements, and downloadable completion certificates',
    ],
  },
]

function detectTag(text) {
  const match = text.match(/\b(New|Improved|Fixed)\b/i)
  if (match) return match[1].charAt(0).toUpperCase() + match[1].slice(1).toLowerCase()
  if (/\b(improved|enhancement|enhanced)\b/i.test(text)) return 'Improved'
  if (/\b(fixed|fix|bug)\b/i.test(text)) return 'Fixed'
  return 'New'
}

function parseChangelog(md) {
  if (!md || typeof md !== 'string') return FALLBACK_RELEASES

  const trimmed = md.trim()
  if (!trimmed.includes('## ')) return FALLBACK_RELEASES

  const sections = trimmed.split(/^## /m).filter(Boolean)
  if (sections.length === 0) return FALLBACK_RELEASES

  const parsed = sections.map((section, idx) => {
    const lines = section.trim().split('\n')
    const heading = lines[0].trim()
    const body = lines.slice(1)

    const versionMatch = heading.match(/v?\d+\.\d+(?:\.\d+)?/i)
    const version = versionMatch
      ? (versionMatch[0].startsWith('v') ? versionMatch[0] : `v${versionMatch[0]}`)
      : `Release ${sections.length - idx}`

    const tag = detectTag(heading)
    let title = heading
      .replace(/^v?\d+\.\d+(?:\.\d+)?\s*[-–—:]\s*/i, '')
      .replace(/\s*\((New|Improved|Fixed)\)\s*/gi, '')
      .replace(/\b(New|Improved|Fixed)\b/gi, '')
      .trim()
    if (!title) title = heading

    let date = ''
    const dateInHeading = heading.match(
      /\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}\b/i
    )
    if (dateInHeading) {
      date = dateInHeading[0]
    } else {
      const dateLine = body.find(l => /^(?:\*\*)?Date(?:\*\*)?:/i.test(l.trim()))
      if (dateLine) {
        date = dateLine.replace(/^(?:\*\*)?Date(?:\*\*)?:\s*/i, '').trim()
      }
    }

    const items = body
      .filter(l => /^[-*]\s+/.test(l.trim()))
      .map(l => l.trim().replace(/^[-*]\s+/, '').replace(/\*\*(.+?)\*\*/g, '$1').trim())

    const dotColor = TAG_META[tag]?.dot || DOT_COLORS[idx % DOT_COLORS.length]

    return {
      version,
      tag,
      date,
      title,
      dotColor,
      items: items.length ? items : [body.filter(l => l.trim() && !l.startsWith('#')).join(' ').trim()].filter(Boolean),
    }
  }).filter(r => r.items.length > 0)

  return parsed.length ? parsed : FALLBACK_RELEASES
}

function ReleaseCard({ release, index }) {
  const meta = TAG_META[release.tag] || TAG_META.New

  return (
    <div
      className="flex gap-5 items-start animate-fx-rise"
      style={{ animationDelay: `${index * 0.06}s` }}
    >
      <div className="flex-shrink-0 w-6 flex justify-center pt-[22px] relative z-10">
        <span
          className="w-3.5 h-3.5 rounded-full bg-surface-950 border-2"
          style={{
            borderColor: release.dotColor,
            boxShadow: `0 0 10px ${release.dotColor}66`,
          }}
        />
      </div>
      <FixitPanel
        padding="p-6"
        className="flex-1 hover:border-accent-cyan/30 transition-colors"
      >
        <div className="flex items-center gap-2.5 mb-1.5 flex-wrap">
          <span className="font-display font-extrabold text-lg text-white">{release.version}</span>
          <span className={`text-[11px] font-bold uppercase tracking-wide px-2 py-0.5 rounded-md border ${meta.bg} ${meta.color} ${meta.border}`}>
            {release.tag}
          </span>
          {release.date && (
            <span className="text-xs text-surface-500 ml-auto">{release.date}</span>
          )}
        </div>
        <h3 className="font-semibold text-base text-surface-100 mb-3.5">{release.title}</h3>
        <div className="flex flex-col gap-2">
          {release.items.map((item, i) => (
            <div key={i} className="flex gap-2.5 text-sm leading-relaxed text-surface-400">
              <span className="shrink-0 mt-0.5" style={{ color: release.dotColor }}>▹</span>
              <span>{item}</span>
            </div>
          ))}
        </div>
      </FixitPanel>
    </div>
  )
}

export default function Changelog() {
  const [changelog, setChangelog] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)

  useEffect(() => {
    api.get('/config/', { silentError: true })
      .then(res => {
        setChangelog(res.data?.platform_config?.changelog || res.data?.changelog || null)
      })
      .catch(() => setError(true))
      .finally(() => setLoading(false))
  }, [])

  const releases = useMemo(() => {
    if (loading) return []
    if (changelog) {
      const parsed = parseChangelog(changelog)
      if (parsed.length) return parsed
    }
    return FALLBACK_RELEASES
  }, [changelog, loading])

  const usingFallback = !loading && !changelog

  return (
    <MarketingPageShell
      narrow
      eyebrow="What's new"
      title={
        <span className="bg-gradient-to-r from-accent-blue via-accent-cyan to-accent-purple bg-clip-text text-transparent">
          Platform updates
        </span>
      }
      subtitle="Stay up to date with the latest improvements, features, and fixes."
    >
      {loading && (
        <div className="flex items-center justify-center py-16">
          <div className="flex flex-col items-center gap-3">
            <div className="w-8 h-8 border-2 border-accent-cyan/30 border-t-accent-cyan rounded-full animate-spin" />
            <span className="text-sm text-surface-500">Loading updates...</span>
          </div>
        </div>
      )}

      {!loading && error && releases.length === 0 && (
        <FixitPanel padding="p-12" className="text-center">
          <Sparkles size={32} className="text-surface-600 mx-auto mb-3" />
          <p className="text-surface-400">Could not load the changelog. Please try again later.</p>
        </FixitPanel>
      )}

      {!loading && releases.length > 0 && (
        <>
          {usingFallback && (
            <p className="text-xs text-surface-500 text-center mb-6">Showing recent platform highlights — live feed will sync when config is available.</p>
          )}
          <div className="relative flex flex-col gap-3.5">
            <div
              aria-hidden="true"
              className="absolute left-[11px] top-3.5 bottom-3.5 w-0.5 bg-gradient-to-b from-accent-blue via-accent-purple to-transparent opacity-40"
            />
            {releases.map((release, index) => (
              <ReleaseCard key={`${release.version}-${index}`} release={release} index={index} />
            ))}
          </div>

          <FixitPanel hero padding="p-9" className="mt-10 text-center relative overflow-hidden">
            <div className="absolute inset-0 bg-gradient-to-br from-accent-cyan/10 via-transparent to-accent-purple/10 pointer-events-none" />
            <div className="relative">
              <p className="text-surface-300 text-sm mb-4">
                Want these updates in your inbox? Start training and we&apos;ll keep you posted.
              </p>
              <Link to="/register" className="btn-primary px-7 py-3 text-sm inline-flex items-center gap-2">
                Get started free
              </Link>
            </div>
          </FixitPanel>
        </>
      )}
    </MarketingPageShell>
  )
}
