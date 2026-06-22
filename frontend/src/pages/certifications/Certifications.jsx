import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Award, ArrowRight, Layers, Clock, ShieldCheck } from 'lucide-react'
import PublicLayout from '../../components/layout/PublicLayout'
import MarketingPageShell from '../../components/MarketingPageShell'
import { FixitPanel } from '../../components/design'
import { usePageTitle } from '../../hooks/usePageTitle'
import { certApi } from '../../api/certifications'

function TrackCard({ t }) {
  return (
    <Link
      to={`/certifications/${t.slug}`}
      className="group fx-panel p-5 flex flex-col hover:border-accent-cyan/40 transition-colors"
    >
      <div className="flex items-center justify-between gap-2 mb-3">
        <span className="text-[11px] font-semibold uppercase tracking-wider text-accent-cyan">{t.code}</span>
        {t.vendor ? (
          <span className="text-[10px] font-medium px-2 py-0.5 rounded-full border border-surface-700 text-surface-400">
            {t.vendor}
          </span>
        ) : null}
      </div>
      <h3 className="font-display font-semibold text-white text-lg leading-snug mb-2 group-hover:text-accent-cyan transition-colors">
        {t.name}
      </h3>
      <p className="text-sm text-surface-400 leading-relaxed flex-1">{t.description}</p>
      <div className="mt-4 pt-3 border-t border-surface-800 flex items-center justify-between text-xs text-surface-500">
        <span className="flex items-center gap-3">
          <span className="flex items-center gap-1"><Layers size={12} /> {t.objective_count} objectives</span>
          <span className="flex items-center gap-1"><ShieldCheck size={12} /> {t.scenario_count} labs</span>
        </span>
        <span className="flex items-center gap-1 text-accent-cyan opacity-0 group-hover:opacity-100 transition-opacity">
          View <ArrowRight size={12} />
        </span>
      </div>
    </Link>
  )
}

export default function Certifications() {
  const [tracks, setTracks] = useState([])
  const [loading, setLoading] = useState(true)

  usePageTitle(
    'Certification Prep Tracks',
    'Objective-mapped, hands-on preparation for RHCSA and more — every exam objective backed by live break-fix labs and a timed mock exam.',
  )

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    certApi
      .list()
      .then((data) => {
        if (!cancelled) setTracks(data?.tracks || [])
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <PublicLayout>
      <MarketingPageShell
        eyebrow="Get certified"
        title="Certification Prep Tracks"
        subtitle="Each track maps every published exam objective to live, hands-on labs you already have access to — then a timed mock exam scores you the way the real one does."
      >
        <FixitPanel className="mb-8 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4" padding="p-5">
          <div className="flex items-start gap-3">
            <Award size={20} className="text-accent-amber mt-0.5 shrink-0" />
            <div>
              <h2 className="font-display font-semibold text-white">Objective-mapped, performance-based</h2>
              <p className="text-sm text-surface-400">
                Track your progress per exam objective, then take a timed mock exam graded on real lab completion.
              </p>
            </div>
          </div>
          <Link to="/verify-certificate" className="btn-secondary text-sm shrink-0">Verify a certificate</Link>
        </FixitPanel>

        {loading ? (
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="fx-panel p-5 h-44 animate-pulse bg-surface-900/40" />
            ))}
          </div>
        ) : tracks.length === 0 ? (
          <div className="text-center py-16 text-surface-500">
            <Award size={32} className="mx-auto mb-3 opacity-50" />
            <p>Certification tracks are coming soon.</p>
          </div>
        ) : (
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
            {tracks.map((t) => (
              <TrackCard key={t.slug} t={t} />
            ))}
          </div>
        )}
      </MarketingPageShell>
    </PublicLayout>
  )
}
