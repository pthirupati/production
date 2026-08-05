// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  holdSpeechUnlock,
  pauseSpeechHoldPrimes,
  releaseSpeechHold,
  reassertSpeechUnlockAfterAwait,
  unlockSpeech,
  _resetSpeechUnlockStateForTests,
  _getSpeechUnlockStateForTests,
} from './useInterviewVoice'

function mockSpeechSynthesis({ speaking = false, pending = false, paused = false } = {}) {
  const speak = vi.fn()
  const cancel = vi.fn()
  const resume = vi.fn()
  window.SpeechSynthesisUtterance = function SpeechSynthesisUtterance(text) {
    this.text = text
    this.volume = 1
    this.rate = 1
    this.pitch = 1
  }
  window.speechSynthesis = {
    speaking,
    pending,
    paused,
    speak,
    cancel,
    resume,
    getVoices: () => [],
  }
  return { speak, cancel, resume }
}

describe('interview speech unlock across startRound', () => {
  beforeEach(() => {
    _resetSpeechUnlockStateForTests()
    vi.useFakeTimers()
  })

  afterEach(() => {
    releaseSpeechHold()
    _resetSpeechUnlockStateForTests()
    vi.useRealTimers()
    delete window.speechSynthesis
  })

  it('holdSpeechUnlock marks gesture unlocked and primes when idle', () => {
    const { speak } = mockSpeechSynthesis()
    holdSpeechUnlock()
    const st = _getSpeechUnlockStateForTests()
    expect(st.holdActive).toBe(true)
    expect(st.gestureUnlocked).toBe(true)
    expect(speak).toHaveBeenCalled()
  })

  it('pauseSpeechHoldPrimes keeps hold active but stops new primes', () => {
    const { speak } = mockSpeechSynthesis()
    holdSpeechUnlock()
    speak.mockClear()
    pauseSpeechHoldPrimes()
    expect(_getSpeechUnlockStateForTests().holdPrimesPaused).toBe(true)
    expect(_getSpeechUnlockStateForTests().holdActive).toBe(true)
    vi.advanceTimersByTime(4000)
    expect(speak).not.toHaveBeenCalled()
  })

  it('reassertSpeechUnlockAfterAwait primes when idle', () => {
    const { speak } = mockSpeechSynthesis()
    reassertSpeechUnlockAfterAwait()
    expect(_getSpeechUnlockStateForTests().gestureUnlocked).toBe(true)
    expect(speak).toHaveBeenCalledTimes(1)
  })

  it('reassert with allowPrime:false resumes unlock without enqueueing', () => {
    const { speak } = mockSpeechSynthesis()
    reassertSpeechUnlockAfterAwait({ allowPrime: false })
    expect(_getSpeechUnlockStateForTests().gestureUnlocked).toBe(true)
    expect(speak).not.toHaveBeenCalled()
  })

  it('reassert skips priming while synth is speaking or primes paused', () => {
    const { speak } = mockSpeechSynthesis({ speaking: true })
    reassertSpeechUnlockAfterAwait()
    expect(speak).not.toHaveBeenCalled()
    expect(_getSpeechUnlockStateForTests().gestureUnlocked).toBe(true)

    const idle = mockSpeechSynthesis()
    holdSpeechUnlock()
    idle.speak.mockClear()
    pauseSpeechHoldPrimes()
    reassertSpeechUnlockAfterAwait()
    expect(idle.speak).not.toHaveBeenCalled()
  })

  it('soft unlockSpeech does not enqueue a prime utterance', () => {
    const { speak } = mockSpeechSynthesis()
    unlockSpeech({ soft: true })
    expect(speak).not.toHaveBeenCalled()
  })
})
