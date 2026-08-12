import { useState } from 'react'
import { Link } from 'react-router-dom'
import { authApi } from '../../api/auth'
import { Mail, ArrowLeft, CheckCircle2, AlertCircle } from 'lucide-react'
import toast from 'react-hot-toast'
import { AuthShell } from '../../components/design'

export default function ForgotPassword() {
  const [email, setEmail] = useState('')
  const [loading, setLoading] = useState(false)
  const [sent, setSent] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await authApi.forgotPassword(email)
      setSent(true)
      toast.success('Check your email')
    } catch (err) {
      setError(err.response?.data?.error || 'Something went wrong. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <AuthShell
      compact
      title="Forgot Password"
      subtitle="Enter your email to receive a password reset link"
      footer={
        <Link to="/login" className="flex items-center justify-center gap-2 text-sm text-surface-400 hover:text-accent-cyan mt-6 transition-colors">
          <ArrowLeft size={14} /> Back to sign in
        </Link>
      }
    >
      {sent ? (
        <div className="text-center py-4">
          <CheckCircle2 size={48} className="text-accent-green mx-auto mb-4" />
          <h2 className="text-lg font-semibold text-white mb-2">Check Your Email</h2>
          {/* The API answers identically whether or not an account exists (audit
              Z2-5), so this copy must not claim an email was definitely sent — that
              would re-create the enumeration oracle in the UI. */}
          <p className="text-surface-400 text-sm mb-4">
            If an account exists for <strong className="text-white">{email}</strong>, a
            password reset link is on its way. The link expires in 1 hour.
          </p>
          <p className="text-surface-500 text-xs">
            Didn&apos;t receive it? Check your spam folder, confirm the address, or{' '}
            <button type="button" onClick={() => setSent(false)} className="text-accent-cyan hover:underline">
              try again
            </button>
          </p>
        </div>
      ) : (
        <>
          {error && (
            <div className="flex items-center gap-2 bg-accent-red/10 border border-accent-red/20 text-accent-red text-sm p-3 rounded-lg mb-6">
              <AlertCircle size={16} />
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label className="block text-sm font-medium text-surface-300 mb-1.5">Email Address</label>
              <div className="relative">
                <Mail size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-surface-500" />
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="input-field pl-10"
                  placeholder="you@example.com"
                  required
                />
              </div>
            </div>

            <button type="submit" disabled={loading} className="btn-primary w-full py-3 disabled:opacity-50">
              {loading ? 'Sending…' : 'Send Reset Link'}
            </button>
          </form>
        </>
      )}
    </AuthShell>
  )
}
