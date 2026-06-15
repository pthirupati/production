import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { authApi } from '../../api/auth'
import { Terminal, AlertCircle, CheckCircle2 } from 'lucide-react'
import toast from 'react-hot-toast'
import { getOAuthRedirectUri } from '../../utils/oauth'

export default function OAuthCallback() {
  const { provider } = useParams()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const [status, setStatus] = useState('processing') // processing | success | error
  const [error, setError] = useState('')
  const [registrationRequired, setRegistrationRequired] = useState(false)
  const [providerEmail, setProviderEmail] = useState('')

  useEffect(() => {
    const code = searchParams.get('code')
    if (!code) {
      setStatus('error')
      setError('No authorization code received. Please try again.')
      return
    }

    const exchange = async () => {
      try {
        const socialConfig = await authApi.getSocialConfig()
        const redirectUri = getOAuthRedirectUri(socialConfig, provider)
        const intent = searchParams.get('state') || sessionStorage.getItem('oauth_intent') || searchParams.get('intent') || 'login'
        sessionStorage.removeItem('oauth_intent')
        if (intent === 'link') {
          await authApi.socialLink(provider, code, redirectUri)
          setStatus('success')
          toast.success(`${provider === 'github' ? 'GitHub' : 'Google'} linked to your profile`)
          setTimeout(() => navigate('/profile', { replace: true }), 800)
          return
        }
        await authApi.socialLogin(provider, code, redirectUri, intent)
        setStatus('success')
        toast.success(
          intent === 'register'
            ? `Account created with ${provider === 'github' ? 'GitHub' : 'Google'}!`
            : `Signed in with ${provider === 'github' ? 'GitHub' : 'Google'}!`
        )
        setTimeout(() => navigate('/dashboard', { replace: true }), 800)
      } catch (err) {
        setStatus('error')
        const data = err.response?.data
        if (data?.error_code === 'registration_required') {
          setError(data.error)
          setRegistrationRequired(true)
          setProviderEmail(data.email || '')
        } else {
          setError(data?.error || 'Authentication failed. Please try again.')
        }
      }
    }

    exchange()
  }, [provider, searchParams, navigate])

  return (
    <div className="min-h-screen bg-surface-950 flex items-center justify-center px-4">
      <div className="w-full max-w-md text-center">
        <div className="mb-8">
          <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-accent-cyan to-brand-600 flex items-center justify-center mx-auto shadow-lg shadow-accent-cyan/20">
            <Terminal size={28} className="text-white" />
          </div>
        </div>

        <div className="glass-card p-8">
          {status === 'processing' && (
            <div className="flex flex-col items-center gap-4">
              <div className="w-10 h-10 border-3 border-accent-cyan/30 border-t-accent-cyan rounded-full animate-spin" />
              <h2 className="text-xl font-semibold text-white">Signing you in…</h2>
              <p className="text-surface-400 text-sm">
                Verifying your {provider === 'github' ? 'GitHub' : 'Google'} account
              </p>
            </div>
          )}

          {status === 'success' && (
            <div className="flex flex-col items-center gap-4 animate-slide-up">
              <CheckCircle2 size={40} className="text-accent-green" />
              <h2 className="text-xl font-semibold text-white">Welcome!</h2>
              <p className="text-surface-400 text-sm">Redirecting to dashboard…</p>
            </div>
          )}

          {status === 'error' && (
            <div className="flex flex-col items-center gap-4 animate-slide-up">
              <AlertCircle size={40} className="text-accent-red" />
              <h2 className="text-xl font-semibold text-white">
                {registrationRequired ? 'Register first' : 'Authentication Failed'}
              </h2>
              <p className="text-surface-400 text-sm">{error}</p>
              <div className="flex flex-wrap gap-3 justify-center mt-2">
                {registrationRequired ? (
                  <>
                    <Link to="/register" className="btn-primary px-6">Create account</Link>
                    <button onClick={() => navigate('/login')} className="btn-secondary px-6">Back to Login</button>
                  </>
                ) : (
                  <button onClick={() => navigate('/login')} className="btn-primary px-6">Back to Login</button>
                )}
              </div>
              {registrationRequired && providerEmail && (
                <p className="text-xs text-surface-500">Use the same email ({providerEmail}) when registering.</p>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
