import { useCallback, useEffect, useRef, useState } from 'react'
import api from '../api/client'

/**
 * Shared data-fetching hook: loading / data / error state plus abort on unmount.
 *
 * Replaces the hand-rolled `useEffect(() => { let alive = true; ... })` pattern
 * that every page reimplements slightly differently. The value here is not
 * saving lines — it's that the cancellation is correct in one place instead of
 * fifteen, so a fast tab-switch stops setting state on an unmounted component.
 *
 * Abort is deliberately tied to unmount and to re-fetch, NOT to a timeout: lab
 * provisioning is slow by design (the client's 45s default exists for it), and
 * a hook-level deadline would kill a legitimately in-flight start request.
 * Callers who want a tighter budget pass one through `config.timeout` — see
 * TIMEOUTS in api/client.js.
 *
 * @param {string|null} url        request path; pass null/'' to skip fetching
 * @param {object}      [options]
 * @param {object}      [options.config]    extra axios config (params, timeout, silentError)
 * @param {boolean}     [options.enabled]   set false to defer the request
 * @param {*}           [options.initialData]
 * @returns {{data,error,loading,forbidden,refetch,cancel}}
 */
export function useFetch(url, options = {}) {
  const { config, enabled = true, initialData = null } = options

  const [data, setData] = useState(initialData)
  const [error, setError] = useState(null)
  // Start in the loading state when we're going to fetch immediately, so the
  // first paint shows a spinner rather than an empty state that flips to a
  // spinner one tick later.
  const [loading, setLoading] = useState(Boolean(url) && enabled)

  const controllerRef = useRef(null)
  // Config is almost always an inline object literal at the call site, which
  // would be a new reference every render and re-fire the effect forever.
  // Keep it in a ref and key the effect off the serialized form instead.
  const configRef = useRef(config)
  configRef.current = config
  const configKey = JSON.stringify(config ?? null)

  const cancel = useCallback(() => {
    controllerRef.current?.abort()
    controllerRef.current = null
  }, [])

  const run = useCallback(async () => {
    if (!url || !enabled) return undefined
    // Supersede any in-flight request for this hook — a rapid param change must
    // not let a slow earlier response land after a fast later one.
    controllerRef.current?.abort()
    const controller = new AbortController()
    controllerRef.current = controller

    setLoading(true)
    setError(null)
    try {
      const res = await api.get(url, { ...configRef.current, signal: controller.signal })
      if (controller.signal.aborted) return undefined
      setData(res.data)
      return res.data
    } catch (err) {
      // An aborted request is not a failure: the component either unmounted or
      // superseded it. Surfacing it would flash an error during normal nav.
      if (controller.signal.aborted || err?.code === 'ERR_CANCELED') return undefined
      setError(err)
      return undefined
    } finally {
      if (!controller.signal.aborted) setLoading(false)
    }
  }, [url, enabled, configKey]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    run()
    return cancel
  }, [run, cancel])

  return {
    data,
    error,
    loading,
    // Convenience flag for the entitlement case, which callers branch on often
    // enough to be worth naming. The client interceptor owns the toast; the
    // hook only reports the fact so a page can render an upgrade prompt.
    forbidden: error?.response?.status === 403,
    refetch: run,
    cancel,
  }
}

export default useFetch
