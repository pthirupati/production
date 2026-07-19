import { useCallback, useEffect, useState } from 'react'
import toast from 'react-hot-toast'

/** Shared load/action pattern for backend-driven simulators. */
export function useSimSession(sessionId, scenarioSlug, api) {
  const [state, setState] = useState(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const refresh = useCallback(async () => {
    try {
      setError('')
      const data = await api.getState(sessionId, scenarioSlug)
      setState(data)
    } catch {
      setError('Could not load console state')
    } finally {
      setLoading(false)
    }
  }, [sessionId, scenarioSlug, api])

  useEffect(() => { refresh() }, [refresh])

  const run = useCallback(async (fnOrAction, payloadOrMsg, okMsg) => {
    if (busy) return null
    setBusy(true)
    try {
      let res
      if (typeof fnOrAction === 'function') {
        res = await fnOrAction()
      } else {
        res = await api.action(sessionId, fnOrAction, payloadOrMsg || {})
      }
      const msg = typeof payloadOrMsg === 'string' ? payloadOrMsg : okMsg
      if (res?.ok === false) toast.error(res.error || 'Action failed')
      else if (msg) toast.success(res?.message || msg)
      if (res?.state) setState(res.state)
      else await refresh()
      return res
    } catch (e) {
      toast.error(e?.response?.data?.error || 'Action failed')
      return null
    } finally {
      setBusy(false)
    }
  }, [busy, sessionId, api, refresh])

  return { state, setState, loading, busy, error, refresh, run }
}
