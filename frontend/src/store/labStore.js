import { create } from 'zustand'

export const useLabStore = create((set, get) => ({
  activeSession: null,
  timeRemaining: 0,
  timerInterval: null,
  onExpireCallback: null,
  /** Session id the timer belongs to — expire must not fire for a previous lab. */
  timerSessionId: null,

  setActiveSession: (session) => set({ activeSession: session }),

  /**
   * Start a countdown timer.
   * @param {number} duration - seconds remaining
   * @param {function} [onExpire] - callback invoked when timer reaches 0
   * @param {string} [sessionId] - lab session this timer is bound to
   */
  startTimer: (duration, onExpire = null, sessionId = null) => {
    // Clear any existing timer first
    const prev = get().timerInterval
    if (prev) clearInterval(prev)

    const boundSessionId = sessionId
    set({
      timeRemaining: duration,
      onExpireCallback: onExpire,
      timerSessionId: boundSessionId,
    })
    const interval = setInterval(() => {
      set((state) => {
        const newTime = state.timeRemaining - 1
        if (newTime <= 0) {
          clearInterval(state.timerInterval)
          // Only fire expire if this timer still belongs to the same session
          // (starting another lab must never run the previous lab's stop/redirect).
          const stillBound =
            !boundSessionId
            || !state.timerSessionId
            || state.timerSessionId === boundSessionId
          if (stillBound && state.onExpireCallback) {
            const cb = state.onExpireCallback
            try { cb() } catch { /* swallow */ }
          }
          return {
            timeRemaining: 0,
            timerInterval: null,
            onExpireCallback: null,
            timerSessionId: null,
          }
        }
        return { timeRemaining: newTime }
      })
    }, 1000)
    set({ timerInterval: interval })
  },

  stopTimer: () => {
    set((state) => {
      if (state.timerInterval) clearInterval(state.timerInterval)
      return {
        timerInterval: null,
        onExpireCallback: null,
        timerSessionId: null,
      }
    })
  },

  clearSession: () =>
    set((state) => {
      if (state.timerInterval) clearInterval(state.timerInterval)
      return {
        activeSession: null,
        timeRemaining: 0,
        timerInterval: null,
        onExpireCallback: null,
        timerSessionId: null,
      }
    }),
}))
