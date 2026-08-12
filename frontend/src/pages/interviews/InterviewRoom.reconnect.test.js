import { describe, it, expect } from 'vitest'
import { mergeStartTranscript } from './InterviewRoom.jsx'

// Audit L420 — reconnect. /start/ is idempotent, so a refresh mid-round returns
// the full transcript AND echoes intro/first_question. These must not double up.

const intro = { id: 'm1', role: 'interviewer', content: 'Welcome.', message_type: 'introduction' }
const q1 = { id: 'm2', role: 'interviewer', content: 'What is a load balancer?', message_type: 'question' }
const a1 = { id: 'm3', role: 'candidate', content: 'It spreads traffic.', message_type: 'text' }

describe('mergeStartTranscript', () => {
  it('appends intro and first question on a fresh start', () => {
    const { messages, resuming } = mergeStartTranscript({
      messages: [],
      intro,
      first_question: q1,
    })
    expect(resuming).toBe(false)
    expect(messages.map(m => m.id)).toEqual(['m1', 'm2'])
  })

  it('does not duplicate the echoed intro/question when resuming', () => {
    const { messages, resuming } = mergeStartTranscript({
      messages: [intro, q1, a1],
      intro,
      first_question: q1,
    })
    expect(resuming).toBe(true)
    // The full prior transcript, each line exactly once.
    expect(messages.map(m => m.id)).toEqual(['m1', 'm2', 'm3'])
  })

  it('still appends a genuinely new outstanding question on resume', () => {
    const q2 = { id: 'm4', role: 'interviewer', content: 'And a reverse proxy?' }
    const { messages, resuming } = mergeStartTranscript({
      messages: [intro, q1, a1],
      intro,
      first_question: q2,
    })
    expect(resuming).toBe(true)
    expect(messages.map(m => m.id)).toEqual(['m1', 'm2', 'm3', 'm4'])
  })

  it('tolerates a missing/empty payload', () => {
    expect(mergeStartTranscript(undefined)).toEqual({ messages: [], resuming: false })
    expect(mergeStartTranscript({}).messages).toEqual([])
  })
})
