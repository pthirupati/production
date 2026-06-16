import { useState, useEffect } from 'react'
import { labApi } from '../api/labs'
import { useAuthStore } from '../store/authStore'
import {
  Trophy, Star, Award, Flame, CheckCircle2,
  Download, Shield, Clock, FileText, Server, Monitor, Globe,
  Database, Cpu, Loader2, Lock, ExternalLink
} from 'lucide-react'
import { SkeletonCard } from '../components/Skeleton'
import toast from 'react-hot-toast'
import { interviewsApi } from '../api/interviews'
import { ACHIEVEMENT_META } from '../utils/constants'
import StickyPageToolbar from '../components/StickyPageToolbar'

const techIcons = { Linux: Server, Docker: Monitor, Networking: Globe, 'Web Servers': Globe, Databases: Database, AWS: Cpu, Kubernetes: Cpu, Security: Shield }

export default function Achievements() {
  const { user } = useAuthStore()
  const [achievements, setAchievements] = useState([])
  const [eligibleTechs, setEligibleTechs] = useState([])
  const [loading, setLoading] = useState(true)
  const [interviewCerts, setInterviewCerts] = useState([])
  const [downloading, setDownloading] = useState(null)

  useEffect(() => {
    Promise.all([
      labApi.getAchievements().catch(() => []),
      labApi.getAchievementsCertificate().catch(() => ({ eligible_technologies: [] })),
      interviewsApi.listCertificates().catch(() => ({ certificates: [] })),
    ]).then(([achData, certData, intCerts]) => {
      setAchievements(achData)
      setEligibleTechs(certData.eligible_technologies || [])
      setInterviewCerts(intCerts.certificates || [])
    }).finally(() => setLoading(false))
  }, [])

  const earned = achievements.filter(a => a.earned)
  const locked = achievements.filter(a => !a.earned)

  const handleDownloadCertificate = async (techSlug, techName) => {
    setDownloading(techSlug)
    try {
      const certData = await labApi.getAchievementsCertificate(techSlug)

      if (certData.error) {
        toast.error(certData.error)
        return
      }

      // Generate printable HTML certificate
      const certHtml = generateCertificateHTML(certData)
      const blob = new Blob([certHtml], { type: 'text/html' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `FixitLab_Certificate_${techName}_${certData.username}.html`
      a.click()
      URL.revokeObjectURL(url)
      toast.success(`${techName} certificate downloaded! A copy has also been sent to your email.`)
    } catch (err) {
      const msg = err?.response?.data?.error || 'Failed to generate certificate'
      if (msg.includes('Complete all scenarios')) {
        const remaining = err?.response?.data?.remaining || 0
        toast.error(`Complete ${remaining} more scenario${remaining > 1 ? 's' : ''} in ${techName} to earn your certificate.`)
      } else {
        toast.error(msg)
      }
    } finally {
      setDownloading(null)
    }
  }

  if (loading) return (
    <div className="max-w-5xl mx-auto space-y-6">
      <SkeletonCard lines={3} />
      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {[...Array(6)].map((_, i) => <SkeletonCard key={i} lines={2} />)}
      </div>
    </div>
  )

  return (
    <div className="max-w-5xl mx-auto space-y-8 animate-fade-in">
      <StickyPageToolbar>
      {/* Header */}
      <div className="relative overflow-hidden glass-card p-6 sm:p-8">
        <div className="absolute inset-0 bg-gradient-to-r from-accent-amber/8 via-transparent to-accent-purple/8" />
        <div className="absolute inset-0 bg-dots-pattern opacity-20" />
        <div className="relative">
          <h1 className="text-2xl sm:text-3xl font-black text-white tracking-tight flex items-center gap-3">
            <Trophy className="text-accent-amber shrink-0" size={28} />
            <span className="bg-gradient-to-r from-accent-amber to-accent-purple bg-clip-text text-transparent">
              Achievements & Certificates
            </span>
          </h1>
          <p className="text-surface-400 mt-2 text-sm">
            {earned.length} of {achievements.length} achievements unlocked
          </p>
        </div>
      </div>
      </StickyPageToolbar>

      {/* ═══ Technology Certificates Section ═══ */}
      <div>
        <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <FileText size={18} className="text-accent-cyan" /> Technology Certificates
        </h2>
        <p className="text-sm text-surface-400 mb-4">
          Complete 100% of scenarios in a technology to earn your certificate. Certificates are sent to your email and can be verified online.
        </p>

        {eligibleTechs.length === 0 ? (
          <div className="glass-card p-8 text-center">
            <Lock size={32} className="mx-auto mb-3 text-surface-600" />
            <p className="text-surface-400 mb-1">No technology subscriptions yet</p>
            <p className="text-xs text-surface-500">Subscribe to a technology and complete all scenarios to earn certificates.</p>
          </div>
        ) : (
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {eligibleTechs.map(tech => {
              const Icon = techIcons[tech.technology] || Server
              const pct = tech.total_scenarios > 0
                ? Math.round((tech.completed / tech.total_scenarios) * 100)
                : 0
              const isComplete = tech.can_generate
              return (
                <div key={tech.slug} className={`glass-card p-5 transition-all duration-300 ${
                  isComplete
                    ? 'border-accent-green/30 bg-accent-green/[0.03] hover:border-accent-green/50'
                    : 'hover:border-surface-600/50'
                }`}>
                  <div className="flex items-center gap-3 mb-3">
                    <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${
                      isComplete ? 'bg-accent-green/20' : 'bg-surface-800'
                    }`}>
                      <Icon size={20} className={isComplete ? 'text-accent-green' : 'text-surface-400'} />
                    </div>
                    <div className="flex-1">
                      <h3 className="font-bold text-white text-sm">{tech.technology}</h3>
                      <p className="text-xs text-surface-500">
                        {tech.completed}/{tech.total_scenarios} scenarios completed
                      </p>
                    </div>
                    {isComplete && (
                      <CheckCircle2 size={20} className="text-accent-green shrink-0" />
                    )}
                  </div>

                  {/* Progress bar */}
                  <div className="w-full h-2 bg-surface-800 rounded-full overflow-hidden mb-3">
                    <div
                      className={`h-full rounded-full transition-all duration-700 ${
                        isComplete
                          ? 'bg-gradient-to-r from-accent-green to-emerald-400'
                          : 'bg-gradient-to-r from-accent-cyan to-accent-blue'
                      }`}
                      style={{ width: `${pct}%` }}
                    />
                  </div>

                  <div className="flex items-center justify-between mb-3">
                    <span className={`text-xs font-bold ${isComplete ? 'text-accent-green' : 'text-accent-cyan'}`}>
                      {pct}% Complete
                    </span>
                    {!isComplete && (
                      <span className="text-[10px] text-surface-500">
                        {tech.total_scenarios - tech.completed} remaining
                      </span>
                    )}
                  </div>

                  {isComplete ? (
                    <button
                      onClick={() => handleDownloadCertificate(tech.slug, tech.technology)}
                      disabled={downloading === tech.slug}
                      className="w-full py-2.5 rounded-lg font-semibold text-center bg-accent-green/10 text-accent-green border border-accent-green/20 hover:bg-accent-green/20 transition-all flex items-center justify-center gap-2 text-sm"
                    >
                      {downloading === tech.slug ? (
                        <Loader2 size={14} className="animate-spin" />
                      ) : (
                        <Download size={14} />
                      )}
                      Download Certificate
                    </button>
                  ) : (
                    <div className="w-full py-2.5 rounded-lg text-center bg-surface-800/50 text-surface-500 border border-surface-700/30 flex items-center justify-center gap-2 text-xs">
                      <Lock size={12} /> Complete all scenarios to unlock
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* Interview certificates */}
      <div>
        <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <Award size={18} className="text-indigo-400" /> Interview Certificates (FIXIT-INT)
        </h2>
        <p className="text-sm text-surface-400 mb-4">
          Earned by clearing all rounds in an AI mock interview campaign. Verifiable and shareable on LinkedIn.
        </p>
        {interviewCerts.length === 0 ? (
          <div className="glass-card p-6 text-center border border-dashed border-surface-700">
            <p className="text-surface-400 text-sm">No interview certificates yet.</p>
            <a href="/interviews" className="text-xs text-indigo-400 hover:underline mt-2 inline-block">Start a mock interview →</a>
          </div>
        ) : (
          <div className="grid sm:grid-cols-2 gap-4">
            {interviewCerts.map(cert => (
              <div key={cert.certificate_id} className="glass-card p-5 border border-indigo-500/20">
                <p className="text-sm font-bold text-white">{cert.technology_name}</p>
                <p className="text-xs text-surface-500 font-mono mt-1">{cert.certificate_id}</p>
                <p className="text-xs text-surface-400 mt-2">
                  {cert.rounds_cleared} rounds · Score {Math.round(cert.overall_score)} · {new Date(cert.issued_at).toLocaleDateString()}
                </p>
                <div className="flex gap-2 mt-3">
                  <a
                    href={`/verify-certificate?certificate_id=${encodeURIComponent(cert.certificate_id)}`}
                    className="text-xs text-indigo-400 hover:underline inline-flex items-center gap-1"
                  >
                    <ExternalLink size={12} /> Verify
                  </a>
                  {cert.linkedin_share_text && (
                    <a
                      href={`https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(`${window.location.origin}${cert.verify_url}`)}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs text-blue-400 hover:underline"
                    >
                      LinkedIn
                    </a>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Progress bar */}
      <div className="glass-card p-5">
        <div className="flex items-center justify-between text-sm mb-2">
          <span className="text-surface-400">Overall Achievement Progress</span>
          <span className="text-white font-semibold">{earned.length}/{achievements.length}</span>
        </div>
        <div className="h-3 bg-surface-800 rounded-full overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-accent-cyan to-accent-amber rounded-full transition-all duration-700"
            style={{ width: `${(earned.length / Math.max(achievements.length, 1)) * 100}%` }}
          />
        </div>
      </div>

      {/* Earned Achievements */}
      {earned.length > 0 && (
        <div>
          <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <Star size={18} className="text-accent-amber" /> Unlocked Achievements
          </h2>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {earned.map(a => {
              const meta = ACHIEVEMENT_META[a.key] || {}
              const Icon = meta.icon || Award
              return (
                <div key={a.key} className={`glass-card p-5 border ${meta.border || 'border-surface-700'} hover:scale-[1.02] transition-all`}>
                  <div className="flex items-start gap-3">
                    <div className={`w-12 h-12 rounded-xl ${meta.bg} flex items-center justify-center shrink-0`}>
                      <Icon size={24} className={meta.color} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <h3 className="text-sm font-semibold text-white">{a.label}</h3>
                      <p className="text-xs text-surface-500 mt-0.5">{meta.desc}</p>
                      <p className="text-[10px] text-surface-600 mt-1.5 flex items-center gap-1">
                        <Clock size={10} />
                        {a.earned_at ? new Date(a.earned_at).toLocaleDateString() : 'Earned'}
                      </p>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Locked Achievements */}
      {locked.length > 0 && (
        <div>
          <h2 className="text-lg font-semibold text-surface-400 mb-4 flex items-center gap-2">
            <Shield size={18} /> Locked Achievements
          </h2>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {locked.map(a => {
              const meta = ACHIEVEMENT_META[a.key] || {}
              const Icon = meta.icon || Award
              return (
                <div key={a.key} className="glass-card p-5 opacity-50 hover:opacity-70 transition-opacity">
                  <div className="flex items-start gap-3">
                    <div className="w-12 h-12 rounded-xl bg-surface-800 flex items-center justify-center shrink-0">
                      <Icon size={24} className="text-surface-600" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <h3 className="text-sm font-semibold text-surface-500">{a.label}</h3>
                      <p className="text-xs text-surface-600 mt-0.5">{meta.desc}</p>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}

function generateCertificateHTML(data) {
  return `<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>FixitLab Certificate - ${data.technology} - ${data.username}</title>
<style>
  @media print { body { -webkit-print-color-adjust: exact; print-color-adjust: exact; } }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { background: #0f172a; font-family: 'Segoe UI', system-ui, sans-serif; color: #e2e8f0; padding: 40px; }
  .cert { max-width: 800px; margin: 0 auto; border: 3px solid #06b6d4; border-radius: 20px; padding: 60px 48px; background: linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #0f172a 100%); position: relative; overflow: hidden; }
  .cert::before { content: ''; position: absolute; top: -100px; right: -100px; width: 300px; height: 300px; background: radial-gradient(circle, rgba(6,182,212,0.08), transparent 70%); border-radius: 50%; }
  .cert::after { content: ''; position: absolute; bottom: -80px; left: -80px; width: 250px; height: 250px; background: radial-gradient(circle, rgba(168,85,247,0.06), transparent 70%); border-radius: 50%; }
  .logo { text-align: center; margin-bottom: 32px; }
  .logo-box { display: inline-block; width: 56px; height: 56px; line-height: 56px; text-align: center; background: linear-gradient(135deg, #06b6d4, #4338ca); border-radius: 14px; font-size: 28px; font-weight: bold; color: white; box-shadow: 0 8px 32px rgba(6,182,212,0.3); }
  h1 { text-align: center; font-size: 32px; background: linear-gradient(90deg, #06b6d4, #a855f7); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin: 0 0 8px; }
  .subtitle { text-align: center; font-size: 14px; color: #94a3b8; text-transform: uppercase; letter-spacing: 3px; margin-bottom: 40px; }
  .user { text-align: center; font-size: 36px; font-weight: bold; color: white; margin: 24px 0 8px; }
  .tech-badge { text-align: center; margin: 16px 0 32px; }
  .tech-badge span { display: inline-block; padding: 8px 24px; background: rgba(6,182,212,0.1); border: 1px solid rgba(6,182,212,0.3); border-radius: 12px; font-size: 18px; font-weight: 600; color: #06b6d4; }
  .stats { display: flex; justify-content: center; gap: 48px; margin: 32px 0; }
  .stat { text-align: center; }
  .stat-val { font-size: 32px; font-weight: bold; color: #06b6d4; }
  .stat-label { font-size: 11px; color: #64748b; text-transform: uppercase; letter-spacing: 1.5px; margin-top: 4px; }
  .completion { text-align: center; margin: 24px 0; padding: 16px; background: rgba(34,197,94,0.08); border: 1px solid rgba(34,197,94,0.2); border-radius: 12px; }
  .completion-text { color: #22c55e; font-weight: 600; font-size: 16px; }
  .footer { text-align: center; margin-top: 40px; font-size: 11px; color: #475569; border-top: 1px solid #334155; padding-top: 20px; line-height: 1.8; }
  .verify-link { color: #06b6d4; text-decoration: none; }
</style>
</head>
<body>
<div class="cert">
  <div class="logo"><span class="logo-box">F</span></div>
  <h1>Certificate of Completion</h1>
  <div class="subtitle">FixitLab Technology Mastery</div>
  <p style="text-align:center;color:#94a3b8;font-size:14px;">This certifies that</p>
  <div class="user">${data.username}</div>
  <p style="text-align:center;color:#64748b;font-size:13px;margin-bottom:8px;">${data.email}</p>
  <p style="text-align:center;color:#94a3b8;font-size:14px;margin:16px 0;">has successfully completed all scenarios in</p>
  <div class="tech-badge"><span>${data.technology}</span></div>
  <div class="stats">
    <div class="stat"><div class="stat-val">${data.scenarios_completed}</div><div class="stat-label">Scenarios Completed</div></div>
    <div class="stat"><div class="stat-val">${data.total_scenarios || data.scenarios_completed}</div><div class="stat-label">Total Scenarios</div></div>
    <div class="stat"><div class="stat-val">${data.total_score}</div><div class="stat-label">Total Score</div></div>
  </div>
  <div class="completion">
    <div class="completion-text">${data.completion_percentage || 100}% Completion Achieved</div>
  </div>
  <div class="footer">
    Certificate ID: <strong>${data.certificate_id}</strong><br>
    Generated on ${new Date(data.generated_at).toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })}<br><br>
    Verify this certificate: <a class="verify-link" href="${typeof window !== 'undefined' ? window.location.origin : ''}/verify-certificate?certificate_id=${encodeURIComponent(data.certificate_id || '')}">Verify online</a><br>
    FixitLab — Hands-on DevOps & Cloud Learning Platform
  </div>
</div>
</body>
</html>`
}
