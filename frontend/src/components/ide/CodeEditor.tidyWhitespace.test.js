import { describe, it, expect } from 'vitest'
import { tidyWhitespace } from './CodeEditor'

describe('tidyWhitespace (format document / format-on-save)', () => {
  it('never changes leading indentation', () => {
    // Regression: the old formatter re-quantized indent to multiples of 4, so
    // this valid 3-space-indented function was dedented into a SyntaxError —
    // and format-on-save meant the broken buffer was what got graded.
    const py = 'def f(x):\n   if x:\n      return 1\n   return 0\n'
    expect(tidyWhitespace(py)).toBe(py)
  })

  it('preserves 2-space indentation used by most JS labs', () => {
    const js = 'function f() {\n  if (x) {\n    return 1\n  }\n}\n'
    expect(tidyWhitespace(js)).toBe(js)
  })

  it('keeps indentation inside template/multiline strings intact', () => {
    const src = 'const s = `\n   three spaces stay\n`\n'
    expect(tidyWhitespace(src)).toBe(src)
  })

  it('strips trailing whitespace', () => {
    expect(tidyWhitespace('a = 1   \nb = 2\t\n')).toBe('a = 1\nb = 2\n')
  })

  it('normalises CRLF and collapses trailing blank lines to one newline', () => {
    expect(tidyWhitespace('a = 1\r\nb = 2\r\n\n\n')).toBe('a = 1\nb = 2\n')
  })

  it('adds a single trailing newline when missing', () => {
    expect(tidyWhitespace('a = 1')).toBe('a = 1\n')
  })

  it('leaves blank/whitespace-only documents alone rather than inventing content', () => {
    expect(tidyWhitespace('')).toBe('')
    expect(tidyWhitespace('   ')).toBe('')
  })

  it('is idempotent', () => {
    const src = 'def f():\n   return 1'
    expect(tidyWhitespace(tidyWhitespace(src))).toBe(tidyWhitespace(src))
  })
})
