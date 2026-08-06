// @vitest-environment jsdom
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'
import { segmenterSources } from './useVirtualBackground.js'

/**
 * The MediaPipe selfie-segmentation model must be served from OUR OWN ORIGIN,
 * with no CDN fallback.
 *
 * The old cdn.jsdelivr.net load never worked in production: gateway/nginx.prod.conf
 * allows `script-src 'self' 'unsafe-inline' 'unsafe-eval' https://checkout.razorpay.com`,
 * so the tag was refused before any request went out and EVERY user silently got
 * the no-model path. The fix is self-hosting (see frontend/scripts/vendor-assets.mjs),
 * not widening the CSP to a public CDN.
 *
 * Segmentation nonetheless stays OPTIONAL: these tests assert the source
 * hygiene, and explicitly assert the no-model degradation is preserved. Making
 * segmentation a hard requirement would newly break the offline preview.
 */
const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'useVirtualBackground.js'), 'utf8')

/**
 * The module with comments removed.
 *
 * The comments deliberately explain the CDN history, so a naive scan of the raw
 * file would flag its own documentation. What matters is that no CDN survives in
 * code the browser actually runs.
 */
const CODE = SRC.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '')

describe('segmenter source resolution', () => {
  it('exposes at least one source and every one is same-origin', () => {
    const sources = segmenterSources()
    expect(sources.length).toBeGreaterThan(0)
    for (const source of sources) {
      expect(source).not.toMatch(/^(https?:)?\/\//)
    }
  })

  it('has no CDN reference in executable code', () => {
    // Not "the CDN is last" but "there is no CDN".
    expect(CODE).not.toMatch(/jsdelivr|unpkg|cdnjs/i)
    // And no absolute URL of any kind — a different CDN would be just as bad.
    // (The `/^https?:\/\//` guard in loadScript survives this: its slashes are
    // regex-escaped, so it is not a literal URL.)
    expect(CODE).not.toMatch(/https?:\/\/[a-z0-9.-]/i)
  })

  it('resolves model weights from the same base as the script', () => {
    // locateFile decides where the .tflite/.wasm siblings come from. If it were
    // pinned to a different constant the weights would be fetched from somewhere
    // other than the copy we actually ship.
    expect(SRC).toMatch(/locateFile:\s*\(file\)\s*=>\s*`\$\{base\}\/\$\{file\}`/)
  })

  it('only sets crossOrigin for remote scripts', () => {
    // crossOrigin='anonymous' on a same-origin path forces a CORS check a plain
    // static server will not satisfy, which would break the self-hosted copy.
    // Now that every source is same-origin this guard should never fire, but it
    // stays so a future VITE_SEGMENTER_URL pointing off-origin still behaves.
    expect(SRC).toMatch(/if \(\/\^https\?:\\\/\\\/\/i\.test\(src\)\) script\.crossOrigin/)
  })

  it('drops a failed script tag so a later attempt is actually retried', () => {
    // loadScript dedupes on `script[src=...]`; without removing the dead tag a
    // retry of the same src would resolve as a false "already loaded".
    expect(SRC).toMatch(/if \(!ok\) script\.remove\(\)/)
  })

  it('keeps segmentation optional — the no-model path still exists', () => {
    // Guard the degradation the audit explicitly warned not to regress. Removing
    // the CDN must not turn a missing model into a broken preview.
    expect(SRC).toMatch(/segmenterUnavailable = true/)
    expect(SRC).toMatch(/function compositeNoModel/)
    expect(SRC).toMatch(/useModel = false/)
  })
})
