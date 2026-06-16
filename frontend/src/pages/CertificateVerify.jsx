import { useState, useEffect } from 'react'
import PublicLayout from '../components/layout/PublicLayout'
import { ShieldCheck, Search, CheckCircle2, XCircle, Award, Loader } from 'lucide-react'
import { useSearchParams } from 'react-router-dom'
import { usePageTitle } from '../hooks/usePageTitle'

export default function CertificateVerify() {
  const [searchParams] = useSearchParams()
  const [certId, setCertId] = useState('')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  usePageTitle('Verify Certificate', 'Verify FixitLab technology or AI mock interview certificates by ID.')

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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams])

  const handleVerify = async (e) => {
    e.preventDefault()
    verifyId(certId)
  }

  return (
    <PublicLayout>
      <div className="max-w-2xl mx-auto px-4 py-16">
        {/* Hero */}
        <div className="text-center mb-10">
          <div className="w-20 h-20 mx-auto mb-6 rounded-2xl bg-gradient-to-br from-accent-cyan/20 to-accent-purple/20 border border-accent-cyan/20 flex items-center justify-center animate-pulse-glow">
            <ShieldCheck size={40} className="text-accent-cyan" />
          </div>
          <h1 className="text-4xl font-bold mb-3 bg-gradient-to-r from-white via-accent-cyan to-accent-purple bg-clip-text text-transparent">
            Verify Certificate
          </h1>
          <p className="text-surface-400 text-lg">
            Enter a FixitLab certificate ID — technology labs (FIXIT-*) or mock interviews (FIXIT-INT-*)
          </p>
        </div>

        {/* Search Form */}
        <form onSubmit={handleVerify} className="glass-card p-6 mb-8">
          <div className="flex gap-3">
            <div className="relative flex-1">
              <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-surface-500" size={18} />
              <input
                type="text"
                value={certId}
                onChange={(e) => setCertId(e.target.value)}
                className="input-field pl-12 py-3 text-lg"
                placeholder="e.g., FIXIT-LINUX-42-20260401 or FIXIT-INT-..."
                required
              />
            </div>
            <button
              type="submit"
              disabled={loading}
              className="btn-primary px-8 py-3 flex items-center gap-2 text-base disabled:opacity-50"
            >
              {loading ? <Loader size={18} className="animate-spin" /> : <ShieldCheck size={18} />}
              Verify
            </button>
          </div>
        </form>

        {/* Error */}
        {error && (
          <div className="glass-card p-6 border-accent-red/30 bg-accent-red/5 animate-slide-up">
            <div className="flex items-center gap-3 text-accent-red">
              <XCircle size={24} />
              <p className="font-medium">{error}</p>
            </div>
          </div>
        )}

        {/* Result */}
        {result && (
          <div className={`glass-card p-8 animate-slide-up ${result.valid ? 'border-accent-green/30 bg-accent-green/5' : 'border-accent-red/30 bg-accent-red/5'}`}>
            <div className="flex items-center gap-4 mb-6">
              {result.valid ? (
                <div className="w-16 h-16 rounded-full bg-accent-green/20 flex items-center justify-center">
                  <CheckCircle2 size={32} className="text-accent-green" />
                </div>
              ) : (
                <div className="w-16 h-16 rounded-full bg-accent-red/20 flex items-center justify-center">
                  <XCircle size={32} className="text-accent-red" />
                </div>
              )}
              <div>
                <h2 className="text-2xl font-bold">
                  {result.valid ? 'Certificate is Valid' : 'Certificate is Invalid'}
                </h2>
                <p className="text-surface-400 text-sm mt-1">
                  {result.valid ? 'This certificate has been verified by FixitLab.' : (result.error || 'This certificate could not be verified.')}
                </p>
              </div>
            </div>

            {result.valid && (
              <div className="grid grid-cols-2 gap-4 border-t border-surface-700/50 pt-6">
                {result.type === 'interview' && (
                  <div className="glass-card p-4 col-span-2 border border-indigo-500/20 bg-indigo-500/5">
                    <p className="text-xs text-indigo-400 uppercase tracking-wide mb-1">Certificate type</p>
                    <p className="font-semibold text-white">AI Mock Interview — {result.rounds_cleared} rounds cleared</p>
                    {result.level && (
                      <p className="text-xs text-surface-400 mt-1">Level: {result.level}</p>
                    )}
                  </div>
                )}
                <div className="glass-card p-4">
                  <p className="text-xs text-surface-500 uppercase tracking-wide mb-1">Certificate Holder</p>
                  <p className="font-semibold text-white">{result.holder_name}</p>
                </div>
                <div className="glass-card p-4">
                  <p className="text-xs text-surface-500 uppercase tracking-wide mb-1">Technology</p>
                  <p className="font-semibold text-accent-cyan">{result.technology}</p>
                </div>
                {result.type !== 'interview' && (
                  <div className="glass-card p-4">
                    <p className="text-xs text-surface-500 uppercase tracking-wide mb-1">Scenarios Completed</p>
                    <p className="font-semibold text-white">{result.scenarios_completed} / {result.total_scenarios}</p>
                  </div>
                )}
                <div className="glass-card p-4">
                  <p className="text-xs text-surface-500 uppercase tracking-wide mb-1">
                    {result.type === 'interview' ? 'Interview Score' : 'Total Score'}
                  </p>
                  <p className="font-semibold text-accent-amber flex items-center gap-1">
                    <Award size={16} /> {result.overall_score ?? result.total_score}{result.type === 'interview' ? '/100' : ' pts'}
                  </p>
                </div>
                <div className="glass-card p-4 col-span-2">
                  <p className="text-xs text-surface-500 uppercase tracking-wide mb-1">Certificate ID</p>
                  <p className="font-mono text-sm text-surface-300">{result.certificate_id}</p>
                </div>
                <div className="glass-card p-4 col-span-2">
                  <p className="text-xs text-surface-500 uppercase tracking-wide mb-1">Issued Date</p>
                  <p className="text-surface-300">{result.issued_date}</p>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </PublicLayout>
  )
}
