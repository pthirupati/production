import { useState } from 'react'
import { Link, useSearchParams, useNavigate } from 'react-router-dom'
import { authApi } from '../../api/auth'
import { Lock, ArrowLeft, CheckCircle2, AlertCircle, ArrowRight } from 'lucide-react'
import toast from 'react-hot-toast'
import { AuthShell } from '../../components/design'

export default function ResetPassword() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const token = searchParams.get('token')

  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [loading, setLoading] = useState(false)
  const [success, setSuccess] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')

    if (password !== confirm) {
      setError('Passwords do not match')
      return
    }
    if (password.length < 8) {
      setError('Password must be at least 8 characters')
      return
    }
    if (!token) {
      setError('Invalid reset link. Please request a new one.')
      return
    }

    setLoading(true)
    try {
      await authApi.resetPassword(token, password)
      setSuccess(true)
      toast.success('Password reset successfully!')
    } catch (err) {
      setError(err.response?.data?.error || 'Reset failed. The link may have expired.')
    } finally {
      setLoading(false)
    }
  }

  if (!token) {
    return (
      <AuthShell compact title="Invalid Reset Link">
        <div className="text-center py-2">
          <AlertCircle size={48} className="text-accent-red mx-auto mb-4" />
          <p className="text-surface-400 mb-4">This password reset link is invalid or has expired.</p>
          <Link to="/forgot-password" className="btn-primary inline-flex items-center gap-2">
            Request New Link <ArrowRight size={16} />
          </Link>
        </div>
      </AuthShell>
    )
  }

  return (
    <AuthShell
      compact
      title="Set New Password"
      subtitle="Enter your new password below"
      footer={
        success ? (
          <button type="button" onClick={() => navigate('/login')} className="btn-primary w-full mt-4 py-3">
            Go to Sign In
          </button>
        ) : (
          <Link to="/login" className="flex items-center justify-center gap-2 text-sm text-surface-400 hover:text-accent-cyan mt-6 transition-colors">
            <ArrowLeft size={14} /> Back to sign in
          </Link>
        )
      }
    >
      {success ? (
        <div className="text-center py-4">
          <CheckCircle2 size={48} className="text-accent-green mx-auto mb-4" />
          <h2 className="text-lg font-semibold text-white mb-2">Password Updated</h2>
          <p className="text-surface-400 text-sm">Your password has been reset. You can now sign in with your new password.</p>
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
              <label className="block text-sm font-medium text-surface-300 mb-1.5">New Password</label>
              <div className="relative">
                <Lock size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-surface-500" />
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="input-field pl-10"
                  placeholder="••••••••"
                  required
                  minLength={8}
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-surface-300 mb-1.5">Confirm Password</label>
              <div className="relative">
                <Lock size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-surface-500" />
                <input
                  type="password"
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                  className="input-field pl-10"
                  placeholder="••••••••"
                  required
                  minLength={8}
                />
              </div>
            </div>

            <button type="submit" disabled={loading} className="btn-primary w-full flex items-center justify-center gap-2 py-3 disabled:opacity-50">
              {loading ? 'Resetting…' : <>Reset Password <ArrowRight size={16} /></>}
            </button>
          </form>
        </>
      )}
    </AuthShell>
  )
}
