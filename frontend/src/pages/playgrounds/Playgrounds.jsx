import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Play, FlaskConical, Zap, ShieldCheck, BookOpen, ArrowRight } from 'lucide-react'
import PublicLayout from '../../components/layout/PublicLayout'
import MarketingPageShell from '../../components/MarketingPageShell'
import { FixitPanel } from '../../components/design'
import { usePageTitle } from '../../hooks/usePageTitle'
import { playgroundApi } from '../../api/playgrounds'
import { PlaygroundIcon, CATEGORY_ORDER } from '../../components/playground/playgroundIcons'

const KIND_BADGE = {
  terminal: { label: 'Interactive', cls: 'text-accent-green bg-accent-green/10 border-accent-green/20' },
  sql: { label: 'Interactive', cls: 'text-accent-green bg-accent-green/10 border-accent-green/20' },
  code: { label: 'Run code', cls: 'text-accent-cyan bg-accent-cyan/10 border-accent-cyan/20' },
  lab_link: { label: 'Guided lab', cls: 'text-accent-amber bg-accent-amber/10 border-accent-amber/20' },
}

function PlaygroundCard({ p }) {
  const isLab = p.kind === 'lab_link'
  // Interactive cards open the playground; lab-link cards go straight to the scenario.
  const to = isLab
    ? (p.scenario_slug ? `/scenarios/${p.scenario_slug}` : '/scenarios')
    : `/playgrounds/${p.slug}`
  const badge = KIND_BADGE[p.kind] || KIND_BADGE.terminal
  return (
    <Link to={to} className="group fx-panel p-5 flex flex-col hover:border-accent-cyan/40 transition-colors">
      <div className="flex items-start justify-between gap-2 mb-3">
        <div className="w-10 h-10 rounded-lg bg-surface-800/70 border border-surface-700 flex items-center justify-center text-accent-cyan group-hover:border-accent-cyan/40 transition-colors">
          <PlaygroundIcon name={p.icon} size={20} />
        </div>
        <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full border ${badge.cls}`}>{badge.label}</span>
      </div>
      <h3 className="font-display font-semibold text-white text-base leading-snug mb-1.5 group-hover:text-accent-cyan transition-colors">
        {p.name}
      </h3>
      <p className="text-sm text-surface-400 leading-relaxed flex-1">{p.tagline}</p>
      <div className="mt-4 flex items-center gap-1.5 text-xs font-medium text-accent-cyan">
        {isLab ? <FlaskConical size={13} /> : <Play size={13} />}
        {isLab ? 'Open guided lab' : 'Launch playground'}
        <ArrowRight size={12} className="opacity-0 group-hover:opacity-100 group-hover:translate-x-0.5 transition-all" />
      </div>
    </Link>
  )
}

export default function Playgrounds() {
  const [playgrounds, setPlaygrounds] = useState([])
  const [loading, setLoading] = useState(true)

  usePageTitle(
    'Free Online Playgrounds',
    'Try Linux, Python, JavaScript, Docker, Kubernetes, SQL and Ansible instantly in your browser — free, no signup, nothing to install.',
  )

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    playgroundApi.list()
      .then((data) => { if (!cancelled) setPlaygrounds(data?.playgrounds || []) })
      .catch(() => {})
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [])

  const byCategory = useMemo(() => {
    const groups = {}
    for (const p of playgrounds) {
      ;(groups[p.category] ||= []).push(p)
    }
    const orderedKeys = [
      ...CATEGORY_ORDER.filter((c) => groups[c]),
      ...Object.keys(groups).filter((c) => !CATEGORY_ORDER.includes(c)),
    ]
    return orderedKeys.map((c) => [c, groups[c]])
  }, [playgrounds])

  return (
    <PublicLayout>
      <MarketingPageShell
        eyebrow="Try it instantly"
        title="Playgrounds"
        subtitle="Run real commands and code in your browser — no account, no install, nothing to clean up. Every playground is free and resets itself when you're done."
      >
        {/* Feature strip */}
        <div className="grid sm:grid-cols-3 gap-3 mb-10">
          {[
            { icon: Zap, title: 'Instant', text: 'Click a card and start typing — no setup.' },
            { icon: ShieldCheck, title: 'Ephemeral', text: 'Sessions are in-memory and auto-expire. Nothing is saved.' },
            { icon: BookOpen, title: 'Guided', text: 'Pair any playground with a free tutorial that teaches it.' },
          ].map(({ icon: Icon, title, text }) => (
            <FixitPanel key={title} padding="p-4" className="flex items-start gap-3">
              <Icon size={18} className="text-accent-purple mt-0.5 shrink-0" />
              <div>
                <p className="font-medium text-surface-100 text-sm">{title}</p>
                <p className="text-xs text-surface-400">{text}</p>
              </div>
            </FixitPanel>
          ))}
        </div>

        {loading ? (
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="fx-panel p-5 h-40 animate-pulse bg-surface-900/40" />
            ))}
          </div>
        ) : (
          <div className="space-y-10">
            {byCategory.map(([category, items]) => (
              <section key={category}>
                <h2 className="font-display text-sm font-semibold uppercase tracking-wider text-surface-400 mb-4">{category}</h2>
                <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
                  {items.map((p) => <PlaygroundCard key={p.slug} p={p} />)}
                </div>
              </section>
            ))}
          </div>
        )}

        {/* Tutorials cross-link */}
        <FixitPanel className="mt-12 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4" padding="p-5">
          <div className="flex items-start gap-3">
            <BookOpen size={20} className="text-accent-cyan mt-0.5 shrink-0" />
            <div>
              <h2 className="font-display font-semibold text-white">New to a tool?</h2>
              <p className="text-sm text-surface-400">Read a short, hands-on tutorial first — then jump into the matching playground.</p>
            </div>
          </div>
          <Link to="/tutorials" className="btn-secondary text-sm shrink-0">Browse Tutorials</Link>
        </FixitPanel>
      </MarketingPageShell>
    </PublicLayout>
  )
}
