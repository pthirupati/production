// @vitest-environment jsdom
//
// Covers the unmount teardown (audit L394/L398) and the locale-keyed voice
// ranking bonus (L2538). The teardown cases assert the SAFE shape specifically:
// the recognizer must be aborted with its handlers already detached, because
// routing through stop()/onend settles the turn as 'manual' and submits an
// empty answer — which React 18 StrictMode would trigger on every dev mount.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { renderHook } from '@testing-library/react'

vi.mock('../api/interviews', () => ({
  interviewsApi: { getVoiceConfig: vi.fn(() => Promise.resolve({})) },
}))

import { useInterviewVoice, _resetSpeechUnlockStateForTests } from './useInterviewVoice'

// Minimal SpeechRecognition double that records how it was shut down.
function installSpeechRecognition() {
  const instances = []
  function FakeSR() {
    this.lang = ''
    this.continuous = false
    this.interimResults = false
    this.onresult = null
    this.onend = null
    this.onerror = null
    this.onspeechstart = null
    this.started = false
    this.stopCalls = 0
    this.abortCalls = 0
    // Snapshot of whether handlers were still attached at abort() time.
    this.handlersAttachedAtAbort = null
    this.start = () => { this.started = true }
    this.stop = () => { this.stopCalls += 1 }
    this.abort = () => {
      this.abortCalls += 1
      this.handlersAttachedAtAbort = !!(this.onend || this.onresult)
    }
    instances.push(this)
  }
  window.SpeechRecognition = FakeSR
  window.webkitSpeechRecognition = FakeSR
  return instances
}

function installSpeechSynthesis() {
  const cancel = vi.fn()
  window.SpeechSynthesisUtterance = function U(text) { this.text = text }
  window.speechSynthesis = {
    speaking: false,
    pending: false,
    paused: false,
    speak: vi.fn(),
    cancel,
    resume: vi.fn(),
    getVoices: () => [],
    onvoiceschanged: null,
  }
  return { cancel }
}

beforeEach(() => {
  _resetSpeechUnlockStateForTests()
  globalThis.fetch = vi.fn(() => Promise.resolve({ json: () => Promise.resolve({}) }))
})

afterEach(() => {
  _resetSpeechUnlockStateForTests()
  delete window.speechSynthesis
  delete window.SpeechRecognition
  delete window.webkitSpeechRecognition
  vi.restoreAllMocks()
})

describe('useInterviewVoice unmount teardown (L394)', () => {
  it('aborts a live recognizer on unmount instead of leaving the mic running', () => {
    const instances = installSpeechRecognition()
    installSpeechSynthesis()

    const { result, unmount } = renderHook(() => useInterviewVoice())
    // Start a hands-free turn; we never resolve it — the room is "listening".
    result.current.listenLive(null, {})
    expect(instances).toHaveLength(1)
    expect(instances[0].started).toBe(true)

    unmount()

    // The mic must actually be released. Before the teardown existed this was 0.
    expect(instances[0].abortCalls).toBe(1)
  })

  it('detaches recognizer handlers BEFORE aborting so no empty answer settles', () => {
    const instances = installSpeechRecognition()
    installSpeechSynthesis()

    const { result, unmount } = renderHook(() => useInterviewVoice())
    const settled = vi.fn()
    result.current.listenLive(null, {}).then(settled)
    const r = instances[0]
    expect(r.onend).toBeTypeOf('function')

    unmount()

    // Handlers were already null when abort() ran — a late onend cannot fire.
    expect(r.handlersAttachedAtAbort).toBe(false)
    expect(r.onend).toBeNull()
    expect(r.onresult).toBeNull()
  })

  it('does not resolve the listenLive promise as a manual (empty) answer', async () => {
    installSpeechRecognition()
    installSpeechSynthesis()

    const { result, unmount } = renderHook(() => useInterviewVoice())
    const settled = vi.fn()
    result.current.listenLive(null, {}).then(settled)

    unmount()
    // Flush microtasks — a settle() would have resolved by now.
    await Promise.resolve()
    await Promise.resolve()

    // Unmount must DISCARD the turn, not hand the room a blank transcript to
    // submit. This is the StrictMode double-mount hazard from the audit note.
    expect(settled).not.toHaveBeenCalled()
  })

  it('cancels in-flight speech synthesis on unmount', () => {
    installSpeechRecognition()
    const { cancel } = installSpeechSynthesis()

    const { unmount } = renderHook(() => useInterviewVoice())
    unmount()

    expect(cancel).toHaveBeenCalled()
  })
})

describe('speechSynthesis.onvoiceschanged cleanup (L398)', () => {
  it('clears our handler on unmount', () => {
    installSpeechRecognition()
    installSpeechSynthesis()

    const { unmount } = renderHook(() => useInterviewVoice())
    expect(window.speechSynthesis.onvoiceschanged).toBeTypeOf('function')

    unmount()
    expect(window.speechSynthesis.onvoiceschanged).toBeNull()
  })

  it('does not clobber a later consumer that took over the single global slot', () => {
    installSpeechRecognition()
    installSpeechSynthesis()

    const { unmount } = renderHook(() => useInterviewVoice())
    // Simulate another mounted consumer overwriting the single-slot handler.
    const other = vi.fn()
    window.speechSynthesis.onvoiceschanged = other

    unmount()
    // Ours is gone, so we must leave theirs alone rather than null it.
    expect(window.speechSynthesis.onvoiceschanged).toBe(other)
  })
})

describe('voice ranking prefers the requested locale, not English (L2538)', () => {
  // These two are deliberately close on the naturalness axis, because that is
  // the only band where the +8 is decisive. "Google Ryan" earns 46 naturalness
  // points ('google' 16 + 'ryan' 31, minus overlap) against plain "Lekha"'s 0;
  // the locale terms then decide it. Under the old unconditional
  // `startsWith('en') += 8` the en-US voice won a hi-IN round 37-36. Keying the
  // bonus to the requested locale flips it to 29-44 for the correct language.
  //
  // A LOUDLY-natural English voice (e.g. "Aria Online (Natural)", ~134 pts)
  // still wins a hi-IN round under both rules — naturalness legitimately
  // outweighs locale by design, so don't use one of those as the fixture or the
  // test passes no matter what the code does.
  const voices = [
    { name: 'Lekha', voiceURI: 'hi-in-lekha', lang: 'hi-IN', localService: true },
    { name: 'Google Ryan', voiceURI: 'en-us-ryan', lang: 'en-US', localService: true },
  ]

  function renderWithVoices() {
    installSpeechRecognition()
    installSpeechSynthesis()
    window.speechSynthesis.getVoices = () => voices
    return renderHook(() => useInterviewVoice())
  }

  it('ranks the hi-IN voice first for a hi-IN locale', () => {
    const { result } = renderWithVoices()
    expect(result.current.naturalVoices('hi-IN')[0].lang).toBe('hi-IN')
  })

  it('still ranks the en-US voice first for an en-US locale', () => {
    const { result } = renderWithVoices()
    expect(result.current.naturalVoices('en-US')[0].lang).toBe('en-US')
  })
})
