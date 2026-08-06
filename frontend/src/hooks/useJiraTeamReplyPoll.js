import { useCallback, useEffect, useRef, useState } from 'react'

/**
 * After a Jira comment schedules a delayed team bot reply, show a pending chip
 * and poll until comments grow (audit §X2a).
 *
 * Gated on document.visibilityState so background tabs do not hammer the API.
 */
export function useJiraTeamReplyPoll() {
  const [pending, setPending] = useState(null)
  const timerRef = useRef(null)
  const stopAtRef = useRef(0)
  const baselineCountRef = useRef(0)
  const reloadRef = useRef(null)

  const clearTimers = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current)
      timerRef.current = null
    }
  }, [])

  useEffect(() => () => clearTimers(), [clearTimers])

  const startPendingPoll = useCallback((teamReply, { commentCount = 0, reload } = {}) => {
    clearTimers()
    if (!teamReply?.scheduled || typeof reload !== 'function') {
      setPending(null)
      return
    }
    const delaySec = Number(teamReply.delay_seconds) || 30
    const author = teamReply.pending_author || 'Team'
    baselineCountRef.current = commentCount
    reloadRef.current = reload
    setPending({ author, delaySeconds: delaySec })
    stopAtRef.current = Date.now() + delaySec * 1000 + 12_000

    const tick = async () => {
      if (Date.now() > stopAtRef.current) {
        setPending(null)
        return
      }
      if (typeof document !== 'undefined' && document.visibilityState === 'hidden') {
        timerRef.current = setTimeout(tick, 4000)
        return
      }
      try {
        const nextCount = await reloadRef.current()
        if (typeof nextCount === 'number' && nextCount > baselineCountRef.current) {
          setPending(null)
          return
        }
      } catch { /* keep polling */ }
      timerRef.current = setTimeout(tick, 4000)
    }

    // Start polling a little before the expected delay so the reply appears promptly.
    timerRef.current = setTimeout(tick, Math.max(1500, delaySec * 1000 - 2500))
  }, [clearTimers])

  return {
    pending,
    startPendingPoll,
    clearPending: () => { clearTimers(); setPending(null) },
  }
}
