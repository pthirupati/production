import { useEffect, useRef, useState } from 'react'
import { Link, useLocation, useParams } from 'react-router-dom'
import { interviewsApi } from '../../api/interviews'
import { Award, TrendingUp, AlertCircle, Share2, Calendar, Download, Linkedin, Printer } from 'lucide-react'
import toast from 'react-hot-toast'

export default function InterviewReport() {
  const { roundId } = useParams()
  const location = useLocation()
  const printRef = useRef(null)
  const [round, setRound] = useState(null)
  const report = location.state?.report || round?.report

  useEffect(() => {
    interviewsApi.getRound(roundId).then(setRound).catch(() => {})
  }, [roundId])

  const r = report || round?.report
  if (!r && !round) return <p className="text-surface-500 p-8">Loading report…</p>
  if (!r) return <p className="text-surface-500 p-8">No report yet.</p>

  const linkedInUrl = () => {
    const text = r.certificate?.linkedin_share_text
      || `I completed a mock interview round on FixitLab — score ${Math.round(r.overall_score || 0)}/100.`
    const url = `${window.location.origin}/verify-certificate`
    return `https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(url)}&summary=${encodeURIComponent(text)}`
  }

  const downloadIcal = async () => {
    try {
      const blob = await interviewsApi.downloadRoundIcal(roundId)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `interview-round-${round?.round_number || roundId}.ics`
      a.click()
      URL.revokeObjectURL(url)
      toast.success('Calendar file downloaded')
    } catch {
      toast.error('Schedule a round first to download calendar invite')
    }
  }

  const printReport = () => {
    const html = `<!DOCTYPE html><html><head><title>Interview Report</title>
<style>body{font-family:system-ui,sans-serif;padding:40px;color:#111}h1{font-size:24px}
.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:20px 0}
.card{border:1px solid #ddd;border-radius:8px;padding:12px;text-align:center}
.label{font-size:10px;text-transform:uppercase;color:#666}.score{font-size:22px;font-weight:bold}
ul{padding-left:20px;font-size:14px;line-height:1.6}</style></head><body>
<h1>FixitLab Interview — Round feedback</h1>
<p>${r.passed ? 'Passed' : 'Complete'} · Overall ${Math.round(r.overall_score || 0)}/100</p>
<div class="grid">
${[['Overall', r.overall_score], ['Technical', r.technical_score], ['Communication', r.communication_score],
  ['Problem solving', r.problem_solving_score], ['Practical', r.practical_score], ['Presence', r.presence_score]]
  .map(([l, v]) => `<div class="card"><div class="label">${l}</div><div class="score">${Math.round(v || 0)}</div></div>`).join('')}
</div>
<p>${r.summary || ''}</p>
<h3>Strengths</h3><ul>${(r.strengths || []).map(s => `<li>${s}</li>`).join('')}</ul>
<h3>Improve</h3><ul>${(r.improvements || []).map(s => `<li>${s}</li>`).join('')}</ul>
</body></html>`
    const w = window.open('', '_blank')
    if (!w) { toast.error('Allow pop-ups to print PDF'); return }
    w.document.write(html)
    w.document.close()
    w.focus()
    w.print()
  }

  return (
    <div ref={printRef} className="max-w-2xl mx-auto space-y-6 animate-fade-in py-4">
      <div>
        <Link to="/interviews" className="text-xs text-surface-500 hover:text-white">← Interviews</Link>
        <h1 className="text-2xl font-bold text-white mt-2">Round feedback</h1>
        <p className={`text-sm mt-1 ${r.passed ? 'text-emerald-400' : 'text-amber-400'}`}>
          {round?.is_sample
            ? 'Sample complete — see your mini feedback below'
            : r.passed
              ? 'Cleared — schedule your next round within 48 hours'
              : 'Keep practicing — review gaps below'}
        </p>
      </div>

      <div className="flex flex-wrap gap-2">
        {round?.scheduled_at && (
          <button type="button" onClick={downloadIcal} className="btn-secondary text-xs py-1.5 px-3 inline-flex items-center gap-1.5">
            <Calendar size={12} /> Add to calendar
          </button>
        )}
        <a href={linkedInUrl()} target="_blank" rel="noopener noreferrer" className="btn-secondary text-xs py-1.5 px-3 inline-flex items-center gap-1.5">
          <Linkedin size={12} /> Share on LinkedIn
        </a>
        <button type="button" onClick={printReport} className="btn-secondary text-xs py-1.5 px-3 inline-flex items-center gap-1.5">
          <Printer size={12} /> Print / PDF
        </button>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
        {[
          ['Overall', r.overall_score],
          ['Technical', r.technical_score],
          ['Communication', r.communication_score],
          ['Problem solving', r.problem_solving_score],
          ['Practical', r.practical_score],
          ['Presence', r.presence_score],
        ].map(([label, val]) => (
          <div key={label} className="glass-card p-3 border border-surface-800 text-center">
            <p className="text-[10px] text-surface-500 uppercase">{label}</p>
            <p className="text-xl font-bold text-white">{Math.round(val || 0)}</p>
          </div>
        ))}
      </div>

      <div className="glass-card p-4 border border-surface-800">
        <p className="text-sm text-surface-300">{r.summary}</p>
      </div>

      <div className="grid sm:grid-cols-2 gap-4">
        <div className="glass-card p-4 border border-emerald-500/20">
          <p className="text-xs font-semibold text-emerald-400 flex items-center gap-1 mb-2">
            <TrendingUp size={14} /> Strengths
          </p>
          <ul className="text-xs text-surface-400 space-y-1 list-disc pl-4">
            {(r.strengths || []).map((s, i) => <li key={i}>{s}</li>)}
          </ul>
        </div>
        <div className="glass-card p-4 border border-amber-500/20">
          <p className="text-xs font-semibold text-amber-400 flex items-center gap-1 mb-2">
            <AlertCircle size={14} /> Improve
          </p>
          <ul className="text-xs text-surface-400 space-y-1 list-disc pl-4">
            {(r.improvements || []).map((s, i) => <li key={i}>{s}</li>)}
          </ul>
        </div>
      </div>

      {(r.study_plan || []).length > 0 && (
        <div className="glass-card p-4 border border-surface-800">
          <p className="text-xs font-semibold text-indigo-400 mb-2">Study plan</p>
          <div className="flex flex-wrap gap-2">
            {r.study_plan.map((item, i) => (
              <Link key={i} to={item.url} className="text-xs px-2 py-1 rounded border border-indigo-500/30 text-indigo-300">
                {item.title}
              </Link>
            ))}
          </div>
        </div>
      )}

      {r.passed && !round?.is_sample && (
        <div className="glass-card p-4 border border-indigo-500/20 flex items-center gap-3">
          <Award className="text-indigo-400" size={20} />
          <p className="text-xs text-surface-400">
            Next round unlocks from your campaign page. Complete all rounds for a shareable certificate.
          </p>
        </div>
      )}

      {round?.is_sample && (
        <div className="glass-card p-5 border border-cyan-500/30 bg-cyan-500/5">
          <p className="text-sm font-semibold text-cyan-300 mb-2">Sample complete — ready for the full experience?</p>
          <p className="text-xs text-surface-400 mb-4">
            Subscribe for 10 full interview attempts per year, 3–5 rounds each, hands-on labs, and FIXIT-INT certificates.
          </p>
          <div className="flex flex-wrap gap-2">
            <Link to="/interviews#interview-plans" className="btn-primary text-xs py-2 px-4">View plans</Link>
            <Link to="/subscriptions" className="btn-secondary text-xs py-2 px-4">My subscriptions</Link>
          </div>
        </div>
      )}

      <Link
        to="/interviews"
        className="inline-flex items-center gap-1 text-sm text-indigo-400 hover:underline"
      >
        <Share2 size={14} /> Back to dashboard
      </Link>
    </div>
  )
}
