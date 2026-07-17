import { useEffect, useRef, useState } from 'react'
import { Link, useLocation, useParams } from 'react-router-dom'
import { interviewsApi } from '../../api/interviews'
import { Award, TrendingUp, AlertCircle, Share2, Calendar, Linkedin, Printer } from 'lucide-react'
import toast from 'react-hot-toast'
import { PageHeader } from '../../components/design'
import CompetencyScorecard from '../../components/interviews/CompetencyScorecard'
import ConfidenceAnalysis from '../../components/interviews/ConfidenceAnalysis'
import AIScorecard from '../../components/interviews/AIScorecard'

function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

export default function InterviewReport() {
  const { roundId } = useParams()
  const location = useLocation()
  const printRef = useRef(null)
  const [round, setRound] = useState(null)
  const [transcript, setTranscript] = useState(null)
  const report = location.state?.report || round?.report

  useEffect(() => {
    interviewsApi.getRound(roundId).then(setRound).catch(() => {})
    interviewsApi.getRoundTranscript(roundId).then(setTranscript).catch(() => {})
  }, [roundId])

  const r = report || round?.report
  if (!r && !round) return <p className="text-surface-500 p-8">Loading report…</p>
  if (!r) return <p className="text-surface-500 p-8">No report yet.</p>

  const linkedInUrl = () => {
    const text = r.certificate?.linkedin_share_text
      || `I completed an AI interview round on FixItLab — score ${Math.round(r.overall_score || 0)}/100.`
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
    const comp = (r.competency_ratings || [])
      .map(c => `<tr><td>${escapeHtml(c.name)}</td><td style="text-align:right">${Math.round(c.score || 0)}</td><td>${escapeHtml(c.rating)}</td></tr>`)
      .join('')
    const conf = r.confidence_analysis || {}
    const recLabel = escapeHtml(r.recommendation_label || '')
    const html = `<!DOCTYPE html><html><head><title>Interview Scorecard</title>
<style>body{font-family:system-ui,sans-serif;padding:40px;color:#111;max-width:760px;margin:auto}
h1{font-size:24px;margin-bottom:4px}h3{margin-top:24px;border-bottom:1px solid #eee;padding-bottom:4px}
.rec{display:inline-block;padding:4px 12px;border-radius:999px;font-weight:bold;border:1px solid #999;margin:8px 0}
.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:16px 0}
.card{border:1px solid #ddd;border-radius:8px;padding:12px;text-align:center}
.label{font-size:10px;text-transform:uppercase;color:#666}.score{font-size:22px;font-weight:bold}
table{width:100%;border-collapse:collapse;font-size:14px;margin-top:8px}
td,th{padding:6px 8px;border-bottom:1px solid #eee;text-align:left}
ul{padding-left:20px;font-size:14px;line-height:1.6}.muted{color:#666;font-size:12px}</style></head><body>
<h1>FixitLab Interview Scorecard</h1>
<p class="muted">${escapeHtml(round?.title || '')} · ${r.passed ? 'Passed' : 'Complete'} · Overall ${Math.round(r.overall_score || 0)}/100</p>
${recLabel ? `<div class="rec">Recommendation: ${recLabel}</div>` : ''}
<div class="grid">
${[['Overall', r.overall_score], ['Technical', r.technical_score], ['Communication', r.communication_score],
  ['Problem solving', r.problem_solving_score], ['Practical', r.practical_score], ['Presence', r.presence_score]]
  .map(([l, v]) => `<div class="card"><div class="label">${escapeHtml(l)}</div><div class="score">${Math.round(v || 0)}</div></div>`).join('')}
</div>
<p>${escapeHtml(r.summary || '')}</p>
${comp ? `<h3>Competency scorecard</h3><table><tr><th>Competency</th><th style="text-align:right">Score</th><th>Rating</th></tr>${comp}</table>` : ''}
${conf.confidence_score != null ? `<h3>Communication & confidence (heuristic)</h3><p>${escapeHtml(conf.summary || '')}</p>
<p class="muted">Confidence ${conf.confidence_score}/100 · ${conf.filler_per_100_words ?? 0} fillers/100 words · ${conf.avg_answer_words ?? 0} avg words/answer</p>` : ''}
${conf.round_narrative ? `<h3>Round narrative</h3><p>${escapeHtml(conf.round_narrative)}</p>` : ''}
${conf.phrase_coaching?.phrases_referenced?.length ? `<h3>Phrases from your answers</h3><p class="muted">${escapeHtml(conf.phrase_coaching.summary_line || '')}</p><ul>${conf.phrase_coaching.phrases_referenced.map(p => `<li>${escapeHtml(p)}</li>`).join('')}</ul>` : ''}
${conf.phrase_coaching?.improvements?.length ? `<h3>Phrase-level coaching</h3><ul>${conf.phrase_coaching.improvements.map(s => `<li>${escapeHtml(s)}</li>`).join('')}</ul>` : ''}
<h3>Strengths</h3><ul>${(r.strengths || []).map(s => `<li>${escapeHtml(s)}</li>`).join('')}</ul>
<h3>Areas to improve</h3><ul>${(r.improvements || []).map(s => `<li>${escapeHtml(s)}</li>`).join('')}</ul>
${(transcript?.transcript || []).length ? `<h3>Transcript</h3>${transcript.transcript.filter(m => m.role !== 'system').map(m => `<p style="font-size:13px"><b>${m.role === 'candidate' ? 'You' : 'Interviewer'}:</b> ${escapeHtml(m.content)}</p>`).join('')}` : ''}
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
      <PageHeader
        eyebrow="AI Interview Studio"
        title="Candidate scorecard"
        subtitle={
          round?.is_sample
            ? 'Sample complete — see your mini feedback below'
            : r.passed
              ? 'Cleared — schedule your next round within 48 hours'
              : 'Keep practicing — review gaps below'
        }
      />

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
          <Printer size={12} /> Download scorecard (PDF)
        </button>
        <Link to="/interviews/analytics" className="btn-secondary text-xs py-1.5 px-3 inline-flex items-center gap-1.5">
          <TrendingUp size={12} /> My progress
        </Link>
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
        {r.confidence_analysis?.round_narrative && (
          <p className="text-xs text-surface-400 mt-3 pt-3 border-t border-surface-800">
            {r.confidence_analysis.round_narrative}
          </p>
        )}
      </div>

      {/* Per-answer STAR gauges + dimension breakdown */}
      <AIScorecard report={r} round={round} />

      {/* Parity: hiring recommendation + per-competency scorecard */}
      <CompetencyScorecard
        recommendation={r.recommendation}
        recommendationLabel={r.recommendation_label}
        competencies={r.competency_ratings}
      />

      {/* Parity: heuristic confidence / communication analysis */}
      <ConfidenceAnalysis analysis={r.confidence_analysis} />

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
          <p className="text-xs font-semibold text-indigo-400 mb-2 flex items-center gap-1.5">
            <TrendingUp size={13} /> Resume-Aligned Next Steps
          </p>
          <p className="text-xs text-surface-500 mb-3">Practice these scenarios to close the gaps identified in your interview.</p>
          <div className="flex flex-wrap gap-2">
            {r.study_plan.map((item, i) => (
              <Link key={i} to={item.url} className="text-xs px-2.5 py-1.5 rounded-lg border border-indigo-500/30 text-indigo-300 hover:bg-indigo-500/10 transition-colors">
                {item.title}
              </Link>
            ))}
          </div>
          {r.resume_alignment_score != null && (
            <div className="mt-3 pt-3 border-t border-surface-700">
              <div className="flex items-center gap-2">
                <span className="text-xs text-surface-500">Resume alignment score:</span>
                <span className={`text-xs font-semibold ${r.resume_alignment_score >= 70 ? 'text-accent-green' : r.resume_alignment_score >= 50 ? 'text-accent-amber' : 'text-accent-red'}`}>
                  {Math.round(r.resume_alignment_score)}/100
                </span>
              </div>
            </div>
          )}
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
