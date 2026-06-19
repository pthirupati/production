import { useEffect, useState } from 'react'
import { useSearchParams, Link } from 'react-router-dom'
import PublicLayout from '../components/layout/PublicLayout'
import MarketingPageShell from '../components/MarketingPageShell'
import { FixitPanel } from '../components/design'
import api from '../api/client'
import { Mail, CheckCircle2, AlertTriangle, Loader2 } from 'lucide-react'

export default function Unsubscribe() {
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token')
  const [status, setStatus] = useState('loading')
  const [message, setMessage] = useState('')

  useEffect(() => {
    if (!token) {
      setStatus('error')
      setMessage('Missing unsubscribe link. Use the link from your email or update preferences in Profile.')
      return
    }
    api.get(`/notifications/unsubscribe/?token=${encodeURIComponent(token)}`)
      .then((res) => {
        setStatus('success')
        setMessage(res.data.message || 'You have been unsubscribed from marketing emails.')
      })
      .catch((err) => {
        setStatus('error')
        setMessage(err.response?.data?.error || 'Could not process unsubscribe request.')
      })
  }, [token])

  return (
    <PublicLayout>
      <MarketingPageShell narrow eyebrow="Email preferences" title="Unsubscribe">
        <FixitPanel padding="p-10" className="text-center max-w-lg mx-auto">
          {status === 'loading' && (
            <>
              <Loader2 className="mx-auto mb-4 text-accent-cyan animate-spin" size={40} />
              <p className="text-surface-300">Processing your request…</p>
            </>
          )}
          {status === 'success' && (
            <>
              <CheckCircle2 className="mx-auto mb-4 text-accent-green" size={48} />
              <h2 className="text-xl font-display font-bold text-white mb-2">Unsubscribed</h2>
              <p className="text-surface-300 mb-6">{message}</p>
              <p className="text-sm text-surface-500">
                You can re-enable subscribe reminders anytime in{' '}
                <Link to="/profile#notifications" className="text-accent-cyan hover:underline">Profile → Notifications</Link>.
              </p>
            </>
          )}
          {status === 'error' && (
            <>
              <AlertTriangle className="mx-auto mb-4 text-accent-amber" size={48} />
              <h2 className="text-xl font-display font-bold text-white mb-2">Unable to unsubscribe</h2>
              <p className="text-surface-300 mb-6">{message}</p>
              <Link to="/profile#notifications" className="inline-flex items-center gap-2 text-accent-cyan hover:underline text-sm">
                <Mail size={14} /> Manage email preferences in Profile
              </Link>
            </>
          )}
        </FixitPanel>
      </MarketingPageShell>
    </PublicLayout>
  )
}
