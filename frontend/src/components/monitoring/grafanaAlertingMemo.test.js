// @vitest-environment jsdom
/**
 * Audit L1407 — `foo || {}` / `foo || []` literals in dep arrays.
 *
 * The idiom mints a fresh identity on every render, so any memo depending on it
 * never hits. These assert the underlying rule directly with `useMemo`, because
 * the failure is about *identity across renders*, which is invisible in rendered
 * markup — a component that re-derives everything on every tick still paints the
 * same pixels. Asserting the recompute count is what actually catches a
 * regression.
 */
import { describe, expect, it } from 'vitest'
import { useMemo } from 'react'
import { renderHook } from '@testing-library/react'

const EMPTY_ARR = Object.freeze([])

describe('L1407 — unstable fallback literals defeat useMemo', () => {
  it('demonstrates the bug: a `|| []` literal recomputes every render', () => {
    let computes = 0
    // `state.rules` is absent, so the fallback governs — a new [] each render.
    const { rerender } = renderHook(({ state }) => {
      const rules = state.rules || []
      return useMemo(() => { computes += 1; return rules.length }, [rules])
    }, { initialProps: { state: {} } })

    rerender({ state: {} })
    rerender({ state: {} })
    // Three renders, three recomputes: the memo never hit.
    expect(computes).toBe(3)
  })

  it('the fix: a hoisted constant fallback makes the memo hit', () => {
    let computes = 0
    const { rerender } = renderHook(({ state }) => {
      const rules = state.rules || EMPTY_ARR
      return useMemo(() => { computes += 1; return rules.length }, [rules])
    }, { initialProps: { state: {} } })

    rerender({ state: {} })
    rerender({ state: {} })
    // Identity is stable across renders, so it computes exactly once.
    expect(computes).toBe(1)
  })

  it('still recomputes when real data actually arrives', () => {
    // The risk of stabilizing identity is freezing stale state on a polled
    // screen. Present data keeps its own identity, so updates still flow.
    let computes = 0
    const { rerender } = renderHook(({ state }) => {
      const rules = state.rules || EMPTY_ARR
      return useMemo(() => { computes += 1; return rules.length }, [rules])
    }, { initialProps: { state: {} } })

    rerender({ state: { rules: [{ id: 'a' }] } })
    expect(computes).toBe(2)
    rerender({ state: { rules: [{ id: 'a' }, { id: 'b' }] } })
    expect(computes).toBe(3)
  })

  it('keeps the hoisted fallback immutable', () => {
    // The documented risk of a shared constant is that an in-place mutation
    // corrupts it for every consumer. Freezing turns that into a loud throw.
    expect(Object.isFrozen(EMPTY_ARR)).toBe(true)
    expect(() => { EMPTY_ARR.push(1) }).toThrow()
  })
})
