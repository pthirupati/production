// @vitest-environment jsdom
//
// listenLive server-STT path: when uses_server_stt && mediaStream, do not require
// browser SpeechRecognition; record via MediaRecorder and POST /stt/transcribe/.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, renderHook, waitFor } from '@testing-library/react'

vi.mock('../api/interviews', () => ({
  interviewsApi: { getVoiceConfig: vi.fn(() => Promise.resolve({})) },
}))

import { useInterviewVoice, _resetSpeechUnlockStateForTests } from './useInterviewVoice'

function installMediaRecorder() {
  const instances = []
  class FakeMediaRecorder {
    constructor(stream, opts) {
      this.stream = stream
      this.opts = opts
      this.state = 'inactive'
      this.ondataavailable = null
      this.onstop = null
      instances.push(this)
    }
    start() {
      this.state = 'recording'
    }
    stop() {
      this.state = 'inactive'
      const blob = new Blob([new Uint8Array(800)], { type: 'audio/webm' })
      if (this.ondataavailable) this.ondataavailable({ data: blob })
      if (this.onstop) this.onstop()
    }
  }
  FakeMediaRecorder.isTypeSupported = () => true
  window.MediaRecorder = FakeMediaRecorder
  return instances
}

function installAudioContext({ level = 0 } = {}) {
  // level 0–1 → byte avg via avg/80 scale used by the hook
  const byteAvg = Math.round(level * 80)
  window.AudioContext = class {
    constructor() {
      this.state = 'running'
    }
    createMediaStreamSource() {
      return { connect: () => {} }
    }
    createAnalyser() {
      return {
        fftSize: 256,
        frequencyBinCount: 128,
        getByteFrequencyData: (arr) => { arr.fill(byteAvg) },
      }
    }
    close() {}
    resume() { return Promise.resolve() }
  }
  window.webkitAudioContext = window.AudioContext
}

function mockFetchWithServerStt() {
  globalThis.fetch = vi.fn((url, init) => {
    const u = String(url)
    if (u.includes('/stt/config/')) {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({
          uses_server_stt: true,
          stt_provider: 'vosk',
        }),
      })
    }
    if (u.includes('/stt/transcribe/')) {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({
          transcript: 'hello from server',
          filtered_text: 'hello from server',
          confidence: 0.9,
          provider: 'vosk',
          is_final: true,
          word_count: 3,
        }),
      })
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve({}) })
  })
}

beforeEach(() => {
  _resetSpeechUnlockStateForTests()
  delete window.SpeechRecognition
  delete window.webkitSpeechRecognition
  mockFetchWithServerStt()
  installMediaRecorder()
  installAudioContext({ level: 0 })
})

afterEach(() => {
  _resetSpeechUnlockStateForTests()
  delete window.MediaRecorder
  delete window.AudioContext
  delete window.webkitAudioContext
  delete window.SpeechRecognition
  delete window.webkitSpeechRecognition
  vi.restoreAllMocks()
})

describe('listenLive server STT path', () => {
  it('returns unsupported when neither server STT nor SpeechRecognition is available', async () => {
    globalThis.fetch = vi.fn(() =>
      Promise.resolve({ ok: true, json: () => Promise.resolve({}) }),
    )
    const { result } = renderHook(() => useInterviewVoice())
    await waitFor(() => expect(result.current.config).toBeTruthy())
    // uses_server_stt stays false with empty configs
    const out = await result.current.listenLive(null, {})
    expect(out.reason).toBe('unsupported')
    expect(out.provider).toBe('none')
  })

  it('does not early-return unsupported when server STT is on and SpeechRecognition is missing', async () => {
    const { result } = renderHook(() => useInterviewVoice())
    await waitFor(() => expect(result.current.config.uses_server_stt).toBe(true))

    const mediaStream = { id: 'fake-stream' }
    let settled
    await act(async () => {
      settled = result.current.listenLive(mediaStream, { maxDuration: 5000, silenceMs: 200 })
    })

    // Still listening — not the unsupported short-circuit.
    expect(result.current.isListening).toBe(true)

    await act(async () => {
      result.current.stopListening()
    })
    const out = await settled
    expect(out.reason).toBe('manual')
    expect(out.transcript).toBe('hello from server')
    expect(out.provider).toBe('vosk')
    expect(globalThis.fetch).toHaveBeenCalledWith(
      '/api/interviews/stt/transcribe/',
      expect.objectContaining({ method: 'POST' }),
    )
  })

  it('discards the server turn on unmount without resolving as a manual answer', async () => {
    const { result, unmount } = renderHook(() => useInterviewVoice())
    await waitFor(() => expect(result.current.config.uses_server_stt).toBe(true))

    const settled = vi.fn()
    await act(async () => {
      result.current.listenLive({ id: 's' }, { maxDuration: 30000 }).then(settled)
    })
    expect(result.current.isListening).toBe(true)

    unmount()
    await Promise.resolve()
    await Promise.resolve()
    expect(settled).not.toHaveBeenCalled()
  })
})
