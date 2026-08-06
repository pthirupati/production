import { promises as fs } from 'fs'
import { describe, expect, it } from 'vitest'

/**
 * Audit L1397 claimed `text-surface-500` body copy lands near 4.0:1 on
 * `bg-surface-950`, under the 4.5:1 WCAG AA threshold.
 *
 * Measuring against the real tokens shows the claim is right about the defect
 * but wrong about the theme. surface-500 on surface-950 is 6.18:1 in DARK mode
 * (passes) and 3.66:1 in LIGHT mode (fails) — the light palette inverts the
 * scale, so --s-950 is white and --s-500 barely moves. The two body-copy call
 * sites were moved to surface-400, which clears AA in both themes.
 *
 * This asserts both halves: the ratios computed from the live CSS variables,
 * and that neither call site has regressed back to surface-500. The token
 * itself is deliberately left alone — it is shared with borders and disabled
 * states where sub-AA is correct.
 */
const readSrc = (rel) => fs.readFile(new URL(rel, import.meta.url), 'utf8')

const AA_BODY_TEXT = 4.5

/** WCAG 2.1 relative luminance (sRGB), then the standard contrast ratio. */
function relativeLuminance([r, g, b]) {
  const channel = (v) => {
    const c = v / 255
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
  }
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)
}

function contrastRatio(fg, bg) {
  const [hi, lo] = [relativeLuminance(fg), relativeLuminance(bg)].sort((a, b) => b - a)
  return (hi + 0.05) / (lo + 0.05)
}

/**
 * Pull the `--s-*` scale out of a theme block in index.css. Values are stored
 * as bare `R G B` triples (tailwind.config.js wraps them in `rgb(... / <alpha>)`),
 * so they parse directly into numbers.
 */
function themeTokens(css, selector) {
  const start = css.indexOf(selector)
  if (start === -1) throw new Error(`theme block not found: ${selector}`)
  const block = css.slice(start, css.indexOf('}', start))
  const tokens = {}
  for (const m of block.matchAll(/--s-(\d+):\s*([\d\s]+?);/g)) {
    tokens[`surface-${m[1]}`] = m[2].trim().split(/\s+/).map(Number)
  }
  return tokens
}

describe('surface token contrast for body copy (audit L1397)', () => {
  const themes = [
    [':root,\n[data-theme="dark"]', 'dark'],
    ['[data-theme="light"]', 'light'],
  ]

  for (const [selector, name] of themes) {
    it(`surface-400 body copy clears AA on surface-950 and surface-900 in ${name} mode`, async () => {
      const css = await readSrc('../styles/index.css')
      const t = themeTokens(css, selector)
      expect(t['surface-400']).toHaveLength(3) // sanity: block parsed

      expect(contrastRatio(t['surface-400'], t['surface-950'])).toBeGreaterThanOrEqual(AA_BODY_TEXT)
      expect(contrastRatio(t['surface-400'], t['surface-900'])).toBeGreaterThanOrEqual(AA_BODY_TEXT)
    })
  }

  it('documents that surface-500 is the token that actually fails, and only in light mode', async () => {
    const css = await readSrc('../styles/index.css')
    const dark = themeTokens(css, ':root,\n[data-theme="dark"]')
    const light = themeTokens(css, '[data-theme="light"]')

    // The audit asserted a dark-mode failure. It is not one.
    expect(contrastRatio(dark['surface-500'], dark['surface-950'])).toBeGreaterThanOrEqual(AA_BODY_TEXT)
    // The real defect: light mode. If a future palette change fixes this, the
    // call-site workaround below can be reconsidered.
    expect(contrastRatio(light['surface-500'], light['surface-950'])).toBeLessThan(AA_BODY_TEXT)
  })
})

describe('body-copy call sites do not use surface-500 (audit L1397)', () => {
  it('AppRouter PageLoader "Loading..." uses an AA-safe token', async () => {
    const src = await readSrc('./AppRouter.jsx')
    const loader = src.slice(src.indexOf('function PageLoader'), src.indexOf('function useHydrated'))
    expect(loader).toContain('Loading...')
    expect(loader).not.toMatch(/className="[^"]*\btext-surface-500\b/)
  })

  it('ErrorBoundary error-message <pre> uses an AA-safe token', async () => {
    const src = await readSrc('../components/ErrorBoundary.jsx')
    const pre = src.slice(src.indexOf('<pre'), src.indexOf('</pre>'))
    expect(pre).toContain('this.state.error.message')
    expect(pre).not.toMatch(/\btext-surface-500\b/)
  })
})
