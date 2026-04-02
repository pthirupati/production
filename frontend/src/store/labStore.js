import { create } from 'zustand'

export const useLabStore = create((set, get) => ({
  activeSession: null,
  timeRemaining: 0,
  timerInterval: null,
  onExpireCallback: null,

  setActiveSession: (session) => set({ activeSession: session }),

  /**
   * Start a countdown timer.
   * @param {number} duration - seconds remaining
   * @param {function} [onExpire] - callback invoked when timer reaches 0
   */
  startTimer: (duration, onExpire = null) => {
    // Clear any existing timer first
    const prev = get().timerInterval
    if (prev) clearInterval(prev)

    set({ timeRemaining: duration, onExpireCallback: onExpire })
    const interval = setInterval(() => {
      set((state) => {
        const newTime = state.timeRemaining - 1
        if (newTime <= 0) {
          clearInterval(state.timerInterval)
          // Fire the expiry callback
          if (state.onExpireCallback) {
            try { state.onExpireCallback() } catch (_) { /* swallow */ }
          }
          return { timeRemaining: 0, timerInterval: null }
        }
        return { timeRemaining: newTime }
      })
    }, 1000)
    set({ timerInterval: interval })
  },

  stopTimer: () => {
    set((state) => {
      if (state.timerInterval) clearInterval(state.timerInterval)
      return { timerInterval: null }
    })
  },

  clearSession: () =>
    set((state) => {
      if (state.timerInterval) clearInterval(state.timerInterval)
      return { activeSession: null, timeRemaining: 0, timerInterval: null, onExpireCallback: null }
    }),
}))
