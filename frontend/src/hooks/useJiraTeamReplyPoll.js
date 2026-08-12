import { useCallback, useEffect, useRef, useState } from 'react'

/**
 * After a Jira comment schedules a delayed team bot reply, show a pending chip
 * with a live countdown and poll until comments grow (audit §X2a).
 *
 * When the tab is hidden we keep counting down but defer API reloads; on focus
 * we immediately reload so a reply delivered while the full Jira view was open
 * still appears on the lab panel.
 */
export function useJiraTeamReplyPoll() {
  const [pending, setPending] = useState(null)
  const timerRef = useRef(null)
  const countdownRef = useRef(null)
  const stopAtRef = useRef(0)
  const expectAtRef = useRef(0)
  const baselineCountRef = useRef(0)
  const reloadRef = useRef(null)

  const clearTimers = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current)
      timerRef.current = null
    }
    if (countdownRef.current) {
      clearInterval(countdownRef.current)
      countdownRef.current = null
    }
  }, [])

  useEffect(() => () => clearTimers(), [clearTimers])

  const startPendingPoll = useCallback((teamReply, { commentCount = 0, reload } = {}) => {
    clearTimers()
    if (!teamReply?.scheduled || typeof reload !== 'function') {
      setPending(null)
      return
    }
    const delaySec = Math.max(1, Number(teamReply.delay_seconds) || 30)
    const author = teamReply.pending_author || 'Team'
    const now = Date.now()
    baselineCountRef.current = commentCount
    reloadRef.current = reload
    expectAtRef.current = now + delaySec * 1000
    stopAtRef.current = expectAtRef.current + 12_000
    setPending({ author, delaySeconds: delaySec, remainingSeconds: delaySec })

    countdownRef.current = setInterval(() => {
      const left = Math.max(0, Math.ceil((expectAtRef.current - Date.now()) / 1000))
      setPending((prev) => (prev ? { ...prev, remainingSeconds: left } : prev))
    }, 250)

    const tick = async () => {
      if (Date.now() > stopAtRef.current) {
        clearTimers()
        setPending(null)
        return
      }
      if (typeof document !== 'undefined' && document.visibilityState === 'hidden') {
        timerRef.current = setTimeout(tick, 2000)
        return
      }
      try {
        const nextCount = await reloadRef.current()
        if (typeof nextCount === 'number' && nextCount > baselineCountRef.current) {
          clearTimers()
          setPending(null)
          return
        }
      } catch { /* keep polling */ }
      const afterExpect = Date.now() >= expectAtRef.current
      timerRef.current = setTimeout(tick, afterExpect ? 1500 : 2500)
    }

    timerRef.current = setTimeout(tick, Math.max(1200, delaySec * 1000 - 2500))
  }, [clearTimers])

  useEffect(() => {
    if (!pending) return undefined
    const onVisible = async () => {
      if (document.visibilityState !== 'visible' || !reloadRef.current) return
      try {
        const nextCount = await reloadRef.current()
        if (typeof nextCount === 'number' && nextCount > baselineCountRef.current) {
          clearTimers()
          setPending(null)
        }
      } catch { /* ignore */ }
    }
    document.addEventListener('visibilitychange', onVisible)
    return () => document.removeEventListener('visibilitychange', onVisible)
  }, [pending, clearTimers])

  return {
    pending,
    startPendingPoll,
    clearPending: () => { clearTimers(); setPending(null) },
  }
}
