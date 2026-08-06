import { describe, it, expect } from 'vitest'
import { findBracketProblems, computeDiagnostics } from './CodeEditor'

const messages = (src, lang) => findBracketProblems(src, lang).map((p) => p.message)

describe('findBracketProblems', () => {
  it('does not flag brackets inside strings', () => {
    // Regression: the old regex counter did `text.match(/\(/g)` over the whole
    // document, so this correct line reported "Unbalanced parentheses".
    expect(messages('print("costs $5 (approx)")\n', 'python')).toEqual([])
  })

  it('does not flag brackets inside comments', () => {
    expect(messages('x = 1  # closes the ) from earlier\n', 'python')).toEqual([])
    expect(messages('const x = 1 // a stray ) here\n', 'javascript')).toEqual([])
    expect(messages('/* a stray ( in a block comment */\nconst y = 2\n', 'javascript')).toEqual([])
  })

  it('does not flag brackets inside python triple-quoted strings', () => {
    expect(messages('doc = """\nunbalanced ( in a docstring\n"""\n', 'python')).toEqual([])
  })

  it('handles escaped quotes without losing track of string state', () => {
    expect(messages('s = "a \\" ( still in string"\n', 'python')).toEqual([])
  })

  it('still reports a genuinely unclosed bracket', () => {
    const probs = findBracketProblems('def f(:\n', 'python')
    expect(probs).toHaveLength(1)
    expect(probs[0].message).toMatch(/Unclosed parenthesis/)
  })

  it('still reports a genuinely unmatched closing bracket', () => {
    const probs = findBracketProblems('x = 1)\n', 'python')
    expect(probs).toHaveLength(1)
    expect(probs[0].message).toMatch(/Unmatched closing parenthesis/)
  })

  it('reports mismatched pairs', () => {
    expect(findBracketProblems('x = [1, 2)\n', 'python').length).toBeGreaterThan(0)
  })

  it('accepts correctly nested brackets', () => {
    expect(messages('f({"a": [1, 2]})\n', 'javascript')).toEqual([])
  })

  it('treats backticks as strings only outside python', () => {
    expect(messages('const s = `an ( unbalanced paren`\n', 'javascript')).toEqual([])
  })
})

describe('computeDiagnostics', () => {
  it('flags leading tabs in python but not valid 3-space indentation', () => {
    const tabbed = computeDiagnostics('def f():\n\treturn 1\n', 'python')
    expect(tabbed.some((d) => /PEP 8/.test(d.message))).toBe(true)

    // 3-space indent is legal Python; the old linter raised a hard 'error'.
    const spaced = computeDiagnostics('def f():\n   return 1\n', 'python')
    expect(spaced).toEqual([])
  })

  it('nags about console.log in JS only, as info severity', () => {
    const js = computeDiagnostics('console.log(1)\n', 'javascript')
    expect(js).toHaveLength(1)
    expect(js[0].severity).toBe('info')

    expect(computeDiagnostics('console.log(1)\n', 'python')).toEqual([])
  })

  it('reports offsets that stay within the document', () => {
    const src = 'def f(:\n    return 1\n'
    computeDiagnostics(src, 'python').forEach((d) => {
      expect(d.from).toBeGreaterThanOrEqual(0)
      expect(d.to).toBeLessThanOrEqual(src.length)
      expect(d.from).toBeLessThanOrEqual(d.to)
    })
  })

  it('returns nothing for clean code', () => {
    expect(computeDiagnostics('def f():\n    return 1\n', 'python')).toEqual([])
  })
})
