// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

/**
 * Pyodide must be served from OUR OWN ORIGIN, with no CDN fallback.
 *
 * This started as an offline bug but was really a production one: the runtime
 * used to load from cdn.jsdelivr.net, and gateway/nginx.prod.conf ships
 *   script-src 'self' 'unsafe-inline' 'unsafe-eval' https://checkout.razorpay.com
 * which does not list jsdelivr on script-src OR connect-src. The browser refused
 * the tag before any request went out, so the "Run" button never worked in prod —
 * it only ever showed the "runtime could not be loaded" banner.
 *
 * The fix is to ship the pinned runtime ourselves (see
 * frontend/scripts/vendor-assets.mjs), NOT to widen the CSP — allowing a public
 * CDN to inject script into this origin is a supply-chain regression.
 *
 * These tests therefore guard two things: that no off-origin source can creep
 * back in, and that the loader still degrades gracefully when the assets are
 * missing.
 */

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'pyodideRunner.js'), 'utf8')

/**
 * The module with comments removed.
 *
 * The comments deliberately explain the CDN history, so a naive scan of the raw
 * file would flag its own documentation. What matters is that no CDN survives in
 * code the browser actually runs.
 */
const CODE = SRC.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '')

// Which script src values are allowed to "load". Everything else fires onerror,
// which is what both a CSP refusal and a 404 look like to the DOM.
let loadable = new Set()
let requested = []

function installScriptStub() {
  const realCreate = document.createElement.bind(document)
  vi.spyOn(document, 'createElement').mockImplementation((tag) => {
    const el = realCreate(tag)
    if (tag !== 'script') return el
    let src = ''
    Object.defineProperty(el, 'src', {
      get: () => src,
      set: (v) => {
        src = v
        requested.push(v)
        // Fire asynchronously, like a real network/CSP outcome.
        queueMicrotask(() => {
          const ok = [...loadable].some((p) => v.startsWith(p))
          if (ok) {
            // A successful pyodide.js defines the global loader.
            window.loadPyodide = async ({ indexURL }) => ({ indexURL })
            el.onload?.()
            el.dispatchEvent(new Event('load'))
          } else {
            el.onerror?.()
            el.dispatchEvent(new Event('error'))
          }
        })
      },
      configurable: true,
    })
    return el
  })
  vi.spyOn(document.head, 'appendChild').mockImplementation((el) => el)
}

async function freshRunner() {
  vi.resetModules()
  return import('./pyodideRunner.js')
}

beforeEach(() => {
  loadable = new Set()
  requested = []
  delete window.loadPyodide
  installScriptStub()
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('pyodide source resolution', () => {
  it('exposes at least one source and every one is same-origin', async () => {
    const { pyodideSources } = await freshRunner()
    const sources = pyodideSources()
    expect(sources.length).toBeGreaterThan(0)
    // A relative path is same-origin; anything with a scheme or protocol-relative
    // prefix is not, and would be refused by the production CSP.
    for (const source of sources) {
      expect(source).not.toMatch(/^(https?:)?\/\//)
    }
  })

  it('has no CDN reference in executable code', () => {
    // The strongest regression guard: not "the CDN is last" but "there is no CDN".
    expect(CODE).not.toMatch(/jsdelivr|unpkg|cdnjs/i)
    // And no absolute URL of any kind — a different CDN would be just as bad.
    expect(CODE).not.toMatch(/https?:\/\/[a-z0-9.-]/i)
  })

  it('pins the runtime version to the copy that actually ships', () => {
    // The pin exists so a runtime bump cannot silently change how submitted
    // Python behaves. Tie it to the dependency that vendor-assets.mjs copies, so
    // bumping one without the other fails here rather than in production.
    const pkg = JSON.parse(readFileSync(join(HERE, '../../../package.json'), 'utf8'))
    const installed = pkg.devDependencies.pyodide
    expect(installed).toBe('0.26.2')
    expect(SRC).toContain(`'v${installed}'`)
  })

  it('loads from the self-hosted copy without any off-origin request', async () => {
    loadable.add('/pyodide/')
    const { getPyodide } = await freshRunner()
    const py = await getPyodide()
    // indexURL must be the same-origin base, or the WASM and stdlib would be
    // resolved somewhere other than the copy we shipped.
    expect(py.indexURL).toBe('/pyodide/')
    expect(requested).toEqual(['/pyodide/pyodide.js'])
    expect(requested.some((u) => /^(https?:)?\/\//.test(u))).toBe(false)
  })

  it('reports runtimeMissing instead of throwing when the assets are absent', async () => {
    // Nothing loadable — e.g. the vendored assets failed to deploy. The IDE must
    // degrade to "submit anyway, the server will grade it", not crash.
    const { runPython } = await freshRunner()
    const res = await runPython('print(1)')
    expect(res.ok).toBe(false)
    expect(res.runtimeMissing).toBe(true)
  })

  it('can retry after a failed load instead of caching the failure', async () => {
    // Regression: the loader deduped on `script[data-pyodide]`, so the dead tag
    // left behind by a refused/404 attempt made every later attempt resolve
    // immediately without ever loading anything. With no CDN fallback left,
    // a transient failure must not permanently disable the Run button.
    const { getPyodide } = await freshRunner()
    await expect(getPyodide()).rejects.toBeTruthy()

    // The asset shows up on a later attempt (slow deploy, flaky first fetch).
    loadable.add('/pyodide/')
    const py = await getPyodide()
    expect(py.indexURL).toBe('/pyodide/')
  })
})
