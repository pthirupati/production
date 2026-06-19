import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { authApi } from '../../api/auth'
import { AlertCircle, CheckCircle2, Loader2 } from 'lucide-react'
import toast from 'react-hot-toast'
import { getOAuthRedirectUri } from '../../utils/oauth'
import { AuthShell } from '../../components/design'

export default function OAuthCallback() {
  const { provider } = useParams()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const [status, setStatus] = useState('processing') // processing | success | error
  const [error, setError] = useState('')
  const [registrationRequired, setRegistrationRequired] = useState(false)
  const [providerEmail, setProviderEmail] = useState('')

  useEffect(() => {
    const oauthError = searchParams.get('error')
    if (oauthError) {
      setStatus('error')
      setError(searchParams.get('error_description') || oauthError)
      return
    }
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
        const VALID_INTENTS = ['login', 'register', 'link']
        const rawIntent = searchParams.get('state') || sessionStorage.getItem('oauth_intent') || searchParams.get('intent') || 'login'
        const intent = VALID_INTENTS.includes(rawIntent) ? rawIntent : 'login'
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

  const providerLabel = provider === 'github' ? 'GitHub' : 'Google'

  const title =
    status === 'processing'
      ? 'Signing you in…'
      : status === 'success'
        ? 'Welcome!'
        : registrationRequired
          ? 'Register first'
          : 'Authentication failed'

  const subtitle =
    status === 'processing'
      ? `Verifying your ${providerLabel} account`
      : status === 'success'
        ? 'Redirecting to your dashboard…'
        : error

  return (
    <AuthShell compact title={title} subtitle={status !== 'error' || registrationRequired ? subtitle : undefined}>
      {status === 'processing' && (
        <div className="flex flex-col items-center gap-4 py-2">
          <Loader2 size={40} className="text-accent-cyan animate-spin" />
        </div>
      )}

      {status === 'success' && (
        <div className="flex flex-col items-center gap-4 py-2 animate-fx-rise">
          <CheckCircle2 size={44} className="text-accent-green" />
        </div>
      )}

      {status === 'error' && (
        <div className="flex flex-col items-center gap-4 animate-fx-rise">
          <AlertCircle size={44} className="text-accent-red" />
          {!registrationRequired && <p className="text-surface-400 text-sm text-center">{error}</p>}
          {registrationRequired && (
            <p className="text-surface-400 text-sm text-center">{error}</p>
          )}
          <div className="flex flex-wrap gap-3 justify-center mt-2">
            {registrationRequired ? (
              <>
                <Link to="/register" className="btn-primary px-6">Create account</Link>
                <button type="button" onClick={() => navigate('/login')} className="btn-secondary px-6">Back to Login</button>
              </>
            ) : (
              <button type="button" onClick={() => navigate('/login')} className="btn-primary px-6">Back to Login</button>
            )}
          </div>
          {registrationRequired && providerEmail && (
            <p className="text-xs text-surface-500">Use the same email ({providerEmail}) when registering.</p>
          )}
        </div>
      )}
    </AuthShell>
  )
}
