import { useState, useEffect } from 'react'
import PublicLayout from '../components/layout/PublicLayout'
import MarketingPageShell from '../components/MarketingPageShell'
import { FixitPanel } from '../components/design'
import { ShieldCheck, Search, CheckCircle2, XCircle, Award, Loader, Linkedin, ExternalLink, Star, Target } from 'lucide-react'
import { useSearchParams } from 'react-router-dom'
import { usePageTitle } from '../hooks/usePageTitle'

export default function CertificateVerify() {
  const [searchParams] = useSearchParams()
  const [certId, setCertId] = useState('')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  usePageTitle('Verify Certificate', 'Verify FixitLab technology or AI interview certificates by ID.')

  const verifyId = async (id) => {
    const trimmed = (id || '').trim()
    if (!trimmed) return
    setLoading(true)
    setError('')
    setResult(null)
    try {
      const res = await fetch(`/api/achievements/certificate/verify/?certificate_id=${encodeURIComponent(trimmed)}`)
      const data = await res.json()
      if (data.error && !('valid' in data)) {
        setError(data.error)
      } else {
        setResult(data)
      }
    } catch {
      setError('Failed to verify certificate. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    const fromUrl = searchParams.get('certificate_id')
    if (fromUrl) {
      setCertId(fromUrl)
      verifyId(fromUrl)
    }
  }, [searchParams])

  const handleVerify = async (e) => {
    e.preventDefault()
    verifyId(certId)
  }

  const linkedInShareUrl = result?.valid
    ? `https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(window.location.href)}`
    : null

  return (
    <PublicLayout>
      <MarketingPageShell
        narrow
        eyebrow="Credentials"
        title="Verify Certificate"
        subtitle={
          <>
            Authenticate any FixitLab certificate — technology labs{' '}
            <span className="text-surface-300 font-mono text-sm">FIXIT-*</span> or AI interviews{' '}
            <span className="text-surface-300 font-mono text-sm">FIXIT-INT-*</span>
          </>
        }
      >
        {/* Search form */}
        <form onSubmit={handleVerify} className="mb-6 animate-fx-rise">
          <FixitPanel>
          <label className="block fx-page-eyebrow mb-3 !text-left">
            Certificate ID
          </label>
          <div className="flex gap-3">
            <div className="relative flex-1">
              <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-surface-500" size={16} />
              <input
                type="text"
                value={certId}
                onChange={(e) => setCertId(e.target.value)}
                className="input-field pl-11 py-3 text-base font-mono"
                placeholder="FIXIT-LINUX-42-20260401"
                required
              />
            </div>
            <button
              type="submit"
              disabled={loading}
              className="btn-primary px-7 py-3 flex items-center gap-2 shrink-0 disabled:opacity-50"
            >
              {loading ? <Loader size={16} className="animate-spin" /> : <ShieldCheck size={16} />}
              {loading ? 'Checking…' : 'Verify'}
            </button>
          </div>
          <p className="text-xs text-surface-600 mt-2.5">
            Certificate IDs are on your FixitLab achievement page and LinkedIn certificate entries.
          </p>
          </FixitPanel>
        </form>

        {/* Error */}
        {error && (
          <FixitPanel className="mb-6 border-accent-red/30 bg-accent-red/5 animate-fx-rise flex items-center gap-3">
            <XCircle size={22} className="text-accent-red shrink-0" />
            <p className="text-accent-red font-medium">{error}</p>
          </FixitPanel>
        )}

        {/* Result: Invalid */}
        {result && !result.valid && (
          <FixitPanel className="border-accent-red/25 bg-accent-red/5 animate-fx-rise text-center">
            <div className="w-16 h-16 rounded-full bg-accent-red/15 border border-accent-red/30 flex items-center justify-center mx-auto mb-4">
              <XCircle size={32} className="text-accent-red" />
            </div>
            {/* A revoked or expired certificate WAS found — it just no longer
                stands. Heading that "Not Found" reads as a typo or a bug and
                hides the fact that it was deliberately withdrawn. */}
            <h2 className="text-2xl font-bold text-white mb-2">
              {result.revoked
                ? 'Certificate Revoked'
                : result.is_expired
                  ? 'Certificate Expired'
                  : 'Certificate Not Found'}
            </h2>
            <p className="text-surface-400">{result.error || 'This certificate ID could not be verified. Check the ID and try again.'}</p>
          </FixitPanel>
        )}

        {/* Result: Valid — certificate card */}
        {result?.valid && (
          <div className="animate-fx-rise space-y-4">
            {/* Certificate document */}
            <FixitPanel padding="p-0" className="overflow-hidden border-accent-green/30">
              {/* Certificate header stripe */}
              <div className="h-2 w-full bg-gradient-to-r from-accent-cyan via-accent-green to-accent-blue" />

              {/* Watermark */}
              <div className="absolute inset-0 flex items-center justify-center pointer-events-none select-none">
                <ShieldCheck size={200} className="text-accent-green/4" />
              </div>

              <div className="relative p-8">
                {/* Valid badge + header */}
                <div className="flex items-start justify-between mb-6">
                  <div className="flex items-center gap-3">
                    <div className="w-12 h-12 rounded-full bg-accent-green/15 border border-accent-green/30 flex items-center justify-center">
                      <CheckCircle2 size={24} className="text-accent-green" />
                    </div>
                    <div>
                      <p className="text-xs text-accent-green font-bold uppercase tracking-widest mb-0.5">Verified Certificate</p>
                      <p className="text-surface-400 text-sm">This credential is authentic</p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="text-[10px] text-surface-500 uppercase tracking-wide">FixitLab</p>
                    <p className="text-xs text-surface-400 font-mono mt-0.5">{result.certificate_id}</p>
                  </div>
                </div>

                {/* Cert type banner */}
                {result.type === 'interview' && (
                  <div className="mb-5 p-3.5 rounded-xl border border-accent-purple/25 bg-accent-purple/8 flex items-center gap-3">
                    <Star size={18} className="text-accent-purple shrink-0" fill="currentColor" />
                    <div>
                      <p className="text-xs text-accent-purple font-bold uppercase tracking-wide">AI Interview Certificate</p>
                      <p className="text-sm text-white font-medium mt-0.5">{result.rounds_cleared} Rounds Cleared{result.level ? ` · ${result.level}` : ''}</p>
                    </div>
                  </div>
                )}
                {result.type !== 'interview' && (
                  <div className="mb-5 p-3.5 rounded-xl border border-accent-cyan/25 bg-accent-cyan/8 flex items-center gap-3">
                    <Target size={18} className="text-accent-cyan shrink-0" />
                    <div>
                      <p className="text-xs text-accent-cyan font-bold uppercase tracking-wide">Technology Lab Certificate</p>
                      <p className="text-sm text-white font-medium mt-0.5">{result.technology}</p>
                    </div>
                  </div>
                )}

                {/* Details grid */}
                <div className="grid grid-cols-2 gap-3">
                  <div className="bg-surface-950/60 rounded-xl p-4 border border-surface-800/50">
                    <p className="text-[10px] text-surface-500 uppercase tracking-wide mb-1.5">Certificate Holder</p>
                    <p className="font-semibold text-white">{result.holder_name}</p>
                  </div>
                  <div className="bg-surface-950/60 rounded-xl p-4 border border-surface-800/50">
                    <p className="text-[10px] text-surface-500 uppercase tracking-wide mb-1.5">Technology</p>
                    <p className="font-semibold text-accent-cyan">{result.technology}</p>
                  </div>
                  {result.type !== 'interview' && (
                    <div className="bg-surface-950/60 rounded-xl p-4 border border-surface-800/50">
                      <p className="text-[10px] text-surface-500 uppercase tracking-wide mb-1.5">Scenarios Completed</p>
                      <p className="font-semibold text-white">{result.scenarios_completed} / {result.total_scenarios}</p>
                    </div>
                  )}
                  <div className="bg-surface-950/60 rounded-xl p-4 border border-surface-800/50">
                    <p className="text-[10px] text-surface-500 uppercase tracking-wide mb-1.5">
                      {result.type === 'interview' ? 'Interview Score' : 'Total Score'}
                    </p>
                    <p className="font-semibold text-accent-amber flex items-center gap-1.5">
                      <Award size={15} />
                      {result.overall_score ?? result.total_score}
                      {result.type === 'interview' ? '/100' : ' pts'}
                    </p>
                  </div>
                  <div className="bg-surface-950/60 rounded-xl p-4 border border-surface-800/50 col-span-2">
                    <p className="text-[10px] text-surface-500 uppercase tracking-wide mb-1.5">Issued Date</p>
                    <p className="text-surface-300">{result.issued_date}</p>
                  </div>
                </div>
              </div>

              {/* Certificate footer stripe */}
              <div className="h-1 w-full bg-gradient-to-r from-accent-purple via-accent-pink to-accent-cyan opacity-30" />
            </FixitPanel>

            {/* Actions */}
            <div className="flex flex-wrap gap-3">
              {linkedInShareUrl && (
                <a
                  href={linkedInShareUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-[#0077b5]/15 border border-[#0077b5]/30 text-[#0a85c2] font-semibold text-sm hover:bg-[#0077b5]/25 transition-colors"
                >
                  <Linkedin size={16} /> Share on LinkedIn
                </a>
              )}
              <button
                type="button"
                onClick={() => { setResult(null); setCertId('') }}
                className="btn-secondary text-sm px-5 py-2.5"
              >
                Verify another
              </button>
            </div>
          </div>
        )}

        {/* Trust indicators */}
        {!result && !loading && (
          <div className="mt-10 grid grid-cols-3 gap-4 animate-fx-rise">
            {[
              { icon: ShieldCheck, label: 'Cryptographically signed', color: 'text-accent-green' },
              { icon: CheckCircle2, label: 'Tamper-proof IDs', color: 'text-accent-cyan' },
              { icon: ExternalLink, label: 'LinkedIn shareable', color: 'text-accent-blue' },
            ].map(({ icon: Icon, label, color }) => (
              <FixitPanel key={label} padding="p-4" className="text-center">
                <Icon size={20} className={`${color} mx-auto mb-2`} />
                <p className="text-xs text-surface-400">{label}</p>
              </FixitPanel>
            ))}
          </div>
        )}
      </MarketingPageShell>
    </PublicLayout>
  )
}
