import { describe, it, expect } from 'vitest'
import {
  assignsRole, statesLimit, isGibberish, analyzePrompt, evaluateExercise,
} from './PromptPlayground.jsx'

/*
 * These mirror backend/tests/test_prompt_eval.py. The client and server rubrics
 * are dual-implemented and the server is the real gate, so any drift here means
 * the UI promises a pass the backend rejects. If you change one, change both.
 */

describe('hint matching is word-boundary, not substring', () => {
  it('does not treat "was a"/"has a" as a role assignment', () => {
    // 'as a ' used to match inside 'was a ', so nearly any past-tense
    // sentence satisfied require_any_role.
    expect(assignsRole('this was a great outage and we learned many things')).toBe(false)
    expect(assignsRole('the team has a runbook for this failure mode')).toBe(false)
  })

  it('does not treat "personal" as a persona', () => {
    expect(assignsRole('give me personal advice about switching teams')).toBe(false)
  })

  it('accepts genuine role assignments the old hardcoded list rejected', () => {
    expect(assignsRole('take on the identity of a veteran kubernetes operator')).toBe(true)
    expect(assignsRole('respond as a principal security engineer')).toBe(true)
    expect(assignsRole('answer from the perspective of a database engineer')).toBe(true)
    expect(assignsRole('you are a senior sre')).toBe(true)
  })

  it('does not find a length limit inside longer words', () => {
    // 'short' matched 'shortcoming', 'limit' matched 'limitations',
    // 'word' matched 'wording' — all false "states a limit" credit.
    expect(statesLimit('rewrite this shortcoming report using clear wording')).toBe(false)
    expect(statesLimit('describe the limitations of this caching approach')).toBe(false)
    expect(statesLimit('unlimited retries are allowed for this job')).toBe(false)
  })

  it('still finds real length limits, including numeric ones', () => {
    expect(statesLimit('keep it short')).toBe(true)
    expect(statesLimit('summarize in under 50 words')).toBe(true)
    expect(statesLimit('rewrite this report in 120 tokens')).toBe(true)
    expect(statesLimit('list the rollback steps in 3 bullets')).toBe(true)
    expect(statesLimit('no more than three sentences')).toBe(true)
  })
})

describe('gibberish padding', () => {
  it('flags keyword-stuffed filler', () => {
    expect(isGibberish('you are xxx yyy zzz aaa bbb ccc ddd eee fff ggg')).toBe(true)
  })

  it('does not flag real prompts, including JSON-shaped ones', () => {
    expect(isGibberish('You are a senior SRE. In 3 bullets, list steps to restart nginx.')).toBe(false)
    expect(isGibberish('You are a data extractor. Return JSON only: {"name": string, "age": int}.')).toBe(false)
  })

  it('ignores short prompts, where the ratio is meaningless', () => {
    expect(isGibberish('summarize this')).toBe(false)
  })
})

describe('evaluateExercise mirrors the server gate', () => {
  it('rejects a role phrase padded with filler', () => {
    const r = evaluateExercise('you are xxx yyy zzz aaa bbb ccc ddd eee fff ggg hhh iii jjj', {
      require_any_role: true, min_words: 10,
    })
    expect(r.passed).toBe(false)
    expect(r.missing).toContain('enough detail')
  })

  it('passes a genuinely good prompt', () => {
    const r = evaluateExercise(
      'You are a senior SRE. In 3 bullet points, list the steps to restart nginx safely.',
      { require_any_role: true, mentions_limit: true, min_words: 8 },
    )
    expect(r.passed).toBe(true)
  })

  it('keeps author-supplied require/any_of terms as substring matches', () => {
    // Scenario YAML ships stems: 'param' -> 'parameter', 'class' -> 'classify',
    // 'cite' -> 'cited'. Word-boundary matching there would un-solve ~150 lessons.
    const r = evaluateExercise(
      'Classify each ticket, show your reasoning, list every cited source, and document each parameter used for validation.',
      { require: [['param']], any_of: [['class'], ['cite'], ['reason'], ['valid']], min_words: 8 },
    )
    expect(r.passed).toBe(true)
  })
})

describe('analyzePrompt quality meter', () => {
  it('does not credit a clear task for word count alone', () => {
    // words >= 6 used to be the whole test, so filler scored a full check.
    const a = analyzePrompt('please help me with this thing okay')
    expect(a.checks.find((c) => c.key === 'task').ok).toBe(false)
  })

  it('credits a clear task when an imperative verb is present', () => {
    const a = analyzePrompt('summarize the incident report for the status page')
    expect(a.checks.find((c) => c.key === 'task').ok).toBe(true)
  })

  it('scores a complete prompt highly and a vague one poorly', () => {
    const good = analyzePrompt(
      'You are a senior SRE. Using the incident timeline below, summarize the root cause in under 50 words as bullet points.',
    )
    const vague = analyzePrompt('tell me about stuff')
    expect(good.score).toBeGreaterThanOrEqual(80)
    expect(vague.score).toBeLessThan(50)
  })
})
