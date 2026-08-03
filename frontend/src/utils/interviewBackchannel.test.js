import { describe, expect, it } from 'vitest'
import { pickBackchannel, BACKCHANNEL_MIN_SPEECH_MS, BACKCHANNEL_THROTTLE_MS } from './interviewBackchannel'

describe('pickBackchannel', () => {
  it('waits for sustained speech', () => {
    let { cue, state } = pickBackchannel({}, { now: 1000, speechActive: true })
    expect(cue).toBeNull()
    ;({ cue, state } = pickBackchannel(state, {
      now: 1000 + BACKCHANNEL_MIN_SPEECH_MS - 100,
      speechActive: true,
    }))
    expect(cue).toBeNull()
  })

  it('fires then throttles', () => {
    const started = 1000
    let { cue, state } = pickBackchannel({}, {
      now: started + BACKCHANNEL_MIN_SPEECH_MS + 10,
      speechActive: true,
      speechStartedAt: started,
    })
    expect(cue).toBeTruthy()
    const first = cue
    ;({ cue, state } = pickBackchannel(state, {
      now: started + BACKCHANNEL_MIN_SPEECH_MS + 500,
      speechActive: true,
    }))
    expect(cue).toBeNull()
    ;({ cue } = pickBackchannel(state, {
      now: started + BACKCHANNEL_MIN_SPEECH_MS + BACKCHANNEL_THROTTLE_MS + 50,
      speechActive: true,
    }))
    expect(cue).toBeTruthy()
    expect(cue).not.toBe(first)
  })
})
