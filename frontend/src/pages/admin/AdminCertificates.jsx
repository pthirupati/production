import { useEffect, useState } from 'react'
import { adminApi } from '../../api/admin'
import { AdminPageHeader } from '../../components/design'
import { Award, Mic2, Trophy, Search } from 'lucide-react'
import toast from 'react-hot-toast'

function StatusPill({ expired, active }) {
  if (expired) {
    return <span className="text-[10px] px-2 py-0.5 rounded-full bg-red-500/10 text-red-400 border border-red-500/20">Expired</span>
  }
  if (active) {
    return <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">Valid</span>
  }
  return <span className="text-[10px] px-2 py-0.5 rounded-full bg-surface-700 text-surface-400">—</span>
}

export default function AdminCertificates() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [email, setEmail] = useState('')
  const [tab, setTab] = useState('technology')

  const load = () => {
    setLoading(true)
    adminApi.getCertificates(email ? { email } : {})
      .then(setData)
      .catch(() => toast.error('Could not load certificates'))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const techCerts = data?.technology_certificates || []
  const interviewCerts = data?.interview_certificates || []
  const achievements = data?.achievements || []

  return (
    <div className="space-y-6">
      <AdminPageHeader
        title="Certificates & Achievements"
        subtitle="Technology completion certs, interview FIXIT-INT certs, and user badges."
        onRefresh={load}
        refreshing={loading}
      />

      <div className="flex flex-wrap gap-2 items-center">
        <div className="relative flex-1 min-w-[200px] max-w-md">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-surface-500" />
          <input
            value={email}
            onChange={e => setEmail(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && load()}
            placeholder="Filter by user email…"
            className="input-field w-full pl-9 text-sm"
          />
        </div>
        <button type="button" onClick={load} className="btn-primary text-sm">Search</button>
      </div>

      <div className="flex flex-wrap gap-2 border-b border-surface-800 pb-2">
        {[
          { id: 'technology', label: `Technology (${techCerts.length})`, icon: Award },
          { id: 'interview', label: `Interview (${interviewCerts.length})`, icon: Mic2 },
          { id: 'achievements', label: `Achievements (${achievements.length})`, icon: Trophy },
        ].map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            type="button"
            onClick={() => setTab(id)}
            className={`px-3 py-1.5 text-xs rounded-lg flex items-center gap-1 ${
              tab === id ? 'bg-accent-cyan/20 text-accent-cyan' : 'text-surface-500 hover:text-surface-300'
            }`}
          >
            <Icon size={12} /> {label}
          </button>
        ))}
      </div>

      {loading ? (
        <p className="text-surface-500 text-sm">Loading…</p>
      ) : (
        <div className="overflow-x-auto">
          {tab === 'technology' && (
            <table className="fx-admin-table">
              <thead>
                <tr className="text-left text-surface-500 border-b border-surface-800">
                  <th className="py-2 pr-4">Certificate ID</th>
                  <th className="py-2 pr-4">User</th>
                  <th className="py-2 pr-4">Technology</th>
                  <th className="py-2 pr-4">Issued</th>
                  <th className="py-2 pr-4">Expires</th>
                  <th className="py-2">Status</th>
                </tr>
              </thead>
              <tbody>
                {techCerts.map(c => (
                  <tr key={c.certificate_id} className="border-b border-surface-800/50 text-surface-300">
                    <td className="py-2 pr-4 font-mono text-xs">{c.certificate_id}</td>
                    <td className="py-2 pr-4 text-xs">{c.user_email}</td>
                    <td className="py-2 pr-4">{c.technology}</td>
                    <td className="py-2 pr-4 text-xs">{c.issued_at ? new Date(c.issued_at).toLocaleDateString() : '—'}</td>
                    <td className="py-2 pr-4 text-xs">{c.expires_at ? new Date(c.expires_at).toLocaleDateString() : '—'}</td>
                    <td className="py-2"><StatusPill expired={c.is_expired} active={!c.is_expired} /></td>
                  </tr>
                ))}
                {techCerts.length === 0 && (
                  <tr><td colSpan={6} className="py-8 text-center text-surface-500">No technology certificates</td></tr>
                )}
              </tbody>
            </table>
          )}

          {tab === 'interview' && (
            <table className="fx-admin-table">
              <thead>
                <tr className="text-left text-surface-500 border-b border-surface-800">
                  <th className="py-2 pr-4">Certificate ID</th>
                  <th className="py-2 pr-4">User</th>
                  <th className="py-2 pr-4">Focus</th>
                  <th className="py-2 pr-4">Level</th>
                  <th className="py-2 pr-4">Score</th>
                  <th className="py-2 pr-4">Expires</th>
                  <th className="py-2">Status</th>
                </tr>
              </thead>
              <tbody>
                {interviewCerts.map(c => (
                  <tr key={c.certificate_id} className="border-b border-surface-800/50 text-surface-300">
                    <td className="py-2 pr-4 font-mono text-xs">{c.certificate_id}</td>
                    <td className="py-2 pr-4 text-xs">{c.user_email}</td>
                    <td className="py-2 pr-4">{c.technology}</td>
                    <td className="py-2 pr-4 text-xs">{c.level || '—'}</td>
                    <td className="py-2 pr-4 text-xs">{c.overall_score?.toFixed?.(0) ?? '—'}</td>
                    <td className="py-2 pr-4 text-xs">{c.expires_at ? new Date(c.expires_at).toLocaleDateString() : '—'}</td>
                    <td className="py-2"><StatusPill expired={c.is_expired} active={!c.is_expired} /></td>
                  </tr>
                ))}
                {interviewCerts.length === 0 && (
                  <tr><td colSpan={7} className="py-8 text-center text-surface-500">No interview certificates</td></tr>
                )}
              </tbody>
            </table>
          )}

          {tab === 'achievements' && (
            <table className="fx-admin-table">
              <thead>
                <tr className="text-left text-surface-500 border-b border-surface-800">
                  <th className="py-2 pr-4">User</th>
                  <th className="py-2 pr-4">Achievement</th>
                  <th className="py-2 pr-4">Code</th>
                  <th className="py-2">Earned</th>
                </tr>
              </thead>
              <tbody>
                {achievements.map((a, i) => (
                  <tr key={`${a.user_id}-${a.achievement_code}-${i}`} className="border-b border-surface-800/50 text-surface-300">
                    <td className="py-2 pr-4 text-xs">{a.user_email}</td>
                    <td className="py-2 pr-4">{a.achievement}</td>
                    <td className="py-2 pr-4 font-mono text-xs">{a.achievement_code}</td>
                    <td className="py-2 text-xs">{a.earned_at ? new Date(a.earned_at).toLocaleString() : '—'}</td>
                  </tr>
                ))}
                {achievements.length === 0 && (
                  <tr><td colSpan={4} className="py-8 text-center text-surface-500">No achievements recorded</td></tr>
                )}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  )
}
