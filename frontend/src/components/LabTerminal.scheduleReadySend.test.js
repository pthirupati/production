import { describe, it, expect, vi } from 'vitest'
import { scheduleReadySend } from './LabTerminal'

// A deterministic fake clock: setTimer records callbacks with an absolute due
// time; advance(ms) runs any callbacks whose due time has passed. This lets us
// drive the bounded poll loop without real timers.
function makeClock() {
  let current = 0
  let seq = 0
  const timers = new Map()
  return {
    now: () => current,
    setTimer: (fn, ms) => {
      const id = ++seq
      timers.set(id, { fn, due: current + Math.max(0, ms) })
      return id
    },
    clearTimer: (id) => { timers.delete(id) },
    advance(ms) {
      const target = current + ms
      // Fire due timers in due-time order until we reach the target time.
      let guard = 0
      for (;;) {
        let next = null
        for (const [id, t] of timers) {
          if (t.due <= target && (!next || t.due < next.due)) next = { id, ...t }
        }
        if (!next) break
        timers.delete(next.id)
        current = next.due
        next.fn()
        if (++guard > 10000) throw new Error('timer loop runaway')
      }
      current = target
    },
  }
}

const connectedTerm = () => ({ isConnected: () => true, sendCommand: vi.fn(() => true) })
const connectingTerm = () => ({ isConnected: () => false, sendCommand: vi.fn(() => false) })

describe('scheduleReadySend', () => {
  it('sends immediately when the terminal is already connected', () => {
    const clock = makeClock()
    const term = connectedTerm()
    const onSuccess = vi.fn()
    const onError = vi.fn()
    scheduleReadySend('ls', {
      getTerminal: () => term, onSuccess, onError,
      now: clock.now, setTimer: clock.setTimer, clearTimer: clock.clearTimer,
      initialDelayMs: 0, intervalMs: 200, timeoutMs: 6000,
    })
    clock.advance(0)
    expect(term.sendCommand).toHaveBeenCalledWith('ls')
    expect(onSuccess).toHaveBeenCalledTimes(1)
    expect(onError).not.toHaveBeenCalled()
  })

  it('polls until the terminal becomes ready, then flushes once', () => {
    const clock = makeClock()
    const term = connectingTerm()
    const onSuccess = vi.fn()
    const onError = vi.fn()
    scheduleReadySend('terraform plan', {
      getTerminal: () => term, onSuccess, onError,
      now: clock.now, setTimer: clock.setTimer, clearTimer: clock.clearTimer,
      initialDelayMs: 150, intervalMs: 150, timeoutMs: 5000,
    })
    // Not connected yet — several ticks, still no send, no error.
    clock.advance(600)
    expect(onSuccess).not.toHaveBeenCalled()
    expect(onError).not.toHaveBeenCalled()
    // Backend shell connects.
    term.isConnected = () => true
    term.sendCommand = vi.fn(() => true)
    clock.advance(300)
    expect(term.sendCommand).toHaveBeenCalledTimes(1)
    expect(onSuccess).toHaveBeenCalledTimes(1)
    // No further sends after resolution.
    clock.advance(2000)
    expect(term.sendCommand).toHaveBeenCalledTimes(1)
    expect(onError).not.toHaveBeenCalled()
  })

  it('errors only after the timeout when the terminal never connects', () => {
    const clock = makeClock()
    const term = connectingTerm()
    const onSuccess = vi.fn()
    const onError = vi.fn()
    scheduleReadySend('nmap -sV host', {
      getTerminal: () => term, onSuccess, onError,
      now: clock.now, setTimer: clock.setTimer, clearTimer: clock.clearTimer,
      initialDelayMs: 0, intervalMs: 200, timeoutMs: 6000,
    })
    clock.advance(5999)
    expect(onError).not.toHaveBeenCalled()
    clock.advance(2)
    expect(onError).toHaveBeenCalledTimes(1)
    expect(onSuccess).not.toHaveBeenCalled()
  })

  it('tolerates a missing terminal ref (host still mounting) without erroring early', () => {
    const clock = makeClock()
    let term = null
    const onSuccess = vi.fn()
    const onError = vi.fn()
    scheduleReadySend('kubectl get pods', {
      getTerminal: () => term, onSuccess, onError,
      now: clock.now, setTimer: clock.setTimer, clearTimer: clock.clearTimer,
      initialDelayMs: 200, intervalMs: 200, timeoutMs: 6000,
    })
    clock.advance(1000)
    expect(onSuccess).not.toHaveBeenCalled()
    expect(onError).not.toHaveBeenCalled()
    // Terminal mounts and connects.
    term = connectedTerm()
    clock.advance(200)
    expect(onSuccess).toHaveBeenCalledTimes(1)
  })

  it('cancel() stops a pending send and reports it was still pending', () => {
    const clock = makeClock()
    const term = connectingTerm()
    const onSuccess = vi.fn()
    const onError = vi.fn()
    const cancel = scheduleReadySend('apt install nginx', {
      getTerminal: () => term, onSuccess, onError,
      now: clock.now, setTimer: clock.setTimer, clearTimer: clock.clearTimer,
      initialDelayMs: 200, intervalMs: 200, timeoutMs: 6000,
    })
    clock.advance(400)
    expect(cancel()).toBe(true)
    // After cancel, advancing past the timeout must not fire onError.
    clock.advance(10000)
    expect(onError).not.toHaveBeenCalled()
    expect(onSuccess).not.toHaveBeenCalled()
    // A second cancel is a no-op.
    expect(cancel()).toBe(false)
  })

  it('cancel() after resolution returns false and does nothing', () => {
    const clock = makeClock()
    const term = connectedTerm()
    const onSuccess = vi.fn()
    const cancel = scheduleReadySend('ls', {
      getTerminal: () => term, onSuccess,
      now: clock.now, setTimer: clock.setTimer, clearTimer: clock.clearTimer,
      initialDelayMs: 0, intervalMs: 200, timeoutMs: 6000,
    })
    clock.advance(0)
    expect(onSuccess).toHaveBeenCalledTimes(1)
    expect(cancel()).toBe(false)
  })
})
