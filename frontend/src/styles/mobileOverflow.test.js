import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import * as csstree from 'css-tree'

// Guards the ≤640px mobile fixes in aws-sim.css / vmware-sim.css (audit
// L1454, L1456). These are pure-CSS layout fixes with no JS to unit test, and
// the previous attempt at them shipped rules keyed to `.vm-table-wrap` /
// `.aws-table-wrap` — classes that appear in zero JSX files, so the CSS was
// dead and the overflow it was meant to fix still happened. Parsing the real
// stylesheet is the only way to catch that class of silent regression.

const read = (name) =>
  readFileSync(fileURLToPath(new URL(`./${name}`, import.meta.url)), 'utf8')

/**
 * Collect declarations from every rule inside a `@media (max-width: <px>)`
 * block whose breakpoint is at least as narrow as `maxWidth` — i.e. the rules
 * that are actually in effect on a phone-sized viewport.
 *
 * @returns {Map<string, Map<string, string>>} selector -> (property -> value)
 */
function mobileRules(css, maxWidth = 640) {
  const ast = csstree.parse(css)
  const out = new Map()

  csstree.walk(ast, {
    visit: 'Atrule',
    enter(atrule) {
      if (atrule.name !== 'media') return
      const query = csstree.generate(atrule.prelude || {})
      const m = /max-width\s*:\s*(\d+)px/.exec(query)
      if (!m || Number(m[1]) > maxWidth) return

      csstree.walk(atrule.block, {
        visit: 'Rule',
        enter(rule) {
          // A rule's prelude may list several comma-separated selectors; each
          // one independently receives the whole declaration block.
          const selectors = csstree
            .generate(rule.prelude)
            .split(',')
            .map((s) => s.trim())
          const decls = new Map()
          csstree.walk(rule.block, {
            visit: 'Declaration',
            enter(decl) {
              decls.set(decl.property, csstree.generate(decl.value).trim())
            },
          })
          for (const sel of selectors) {
            const existing = out.get(sel) || new Map()
            for (const [k, v] of decls) existing.set(k, v)
            out.set(sel, existing)
          }
        },
      })
    },
  })

  return out
}

/** Selectors that scroll a table by matching its real parent via :has(). */
function hasScrollParentFor(rules, tableClass) {
  for (const [sel, decls] of rules) {
    if (!sel.includes(':has(') || !sel.includes(tableClass)) continue
    if (decls.get('overflow-x') === 'auto') return true
  }
  return false
}

describe('vmware-sim.css mobile table overflow (audit L1454)', () => {
  const rules = mobileRules(read('vmware-sim.css'))

  it('drops the 520px .vm-table floor below 640px', () => {
    expect(rules.get('.vm-table')?.get('min-width')).toBe('0')
  })

  it('scrolls the table via a selector that matches real markup', () => {
    // The regression this catches: `.vm-table-wrap { overflow-x: auto }` is
    // syntactically fine but matches nothing, because all 43
    // `<table className="vm-table">` elements are bare children of their panel
    // div. min-width:0 alone does not stop overflow — `.vm-table th` sets
    // white-space: nowrap, so min-content still exceeds a 375px viewport.
    expect(hasScrollParentFor(rules, '.vm-table')).toBe(true)
  })
})

describe('aws-sim.css mobile layout (audit L1454, L1456)', () => {
  const rules = mobileRules(read('aws-sim.css'))

  it('lets .aws-modal shrink below its 400px base min-width', () => {
    const modal = rules.get('.aws-modal')
    expect(modal?.get('min-width')).toBe('0')
    expect(modal?.get('max-width')).toBe('100%')
  })

  it('collapses .aws-leftnav to a rail, not merely a narrower nav', () => {
    // 220px base was 59% of a 375px viewport; the first attempt at this item
    // shrank it to 148px, still 39.5% — a shrink, not a collapse. Require the
    // resting footprint to be a genuine rail while staying >= the 44px WCAG
    // 2.5.5 touch target.
    const nav = rules.get('.aws-leftnav')
    const width = Number(/^(\d+)px$/.exec(nav?.get('width') || '')?.[1])
    expect(width).toBeGreaterThanOrEqual(44)
    expect(width).toBeLessThanOrEqual(56)
    expect(nav?.get('min-width')).toBe(`${width}px`)
  })

  it('expands the rail on hover AND on keyboard focus, as an overlay', () => {
    // Overlaying is what makes it a real collapse: expanding must not steal
    // width back from the content pane. focus-within is required so the nav is
    // reachable without a pointer.
    for (const sel of ['.aws-leftnav:hover', '.aws-leftnav:focus-within']) {
      const decls = rules.get(sel)
      expect(decls, `missing rule for ${sel}`).toBeTruthy()
      expect(decls.get('position')).toBe('absolute')
      expect(Number(/^(\d+)px$/.exec(decls.get('width') || '')?.[1])).toBeGreaterThan(150)
    }
  })

  it('scrolls .aws-table via a selector that matches real markup', () => {
    expect(hasScrollParentFor(rules, '.aws-table')).toBe(true)
  })
})
