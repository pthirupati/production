// @vitest-environment jsdom
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { composeHtmlPreview, PREVIEW_LOG_TYPE } from './composeHtmlPreview'

/**
 * Execute the injected shim for real instead of asserting on its source text.
 *
 * We pull the bridge <script> out of the composed document and run it with a
 * stubbed `parent`/`console`/`window`, which is what it actually sees inside the
 * sandboxed iframe.
 */
function runBridge(doc) {
  const start = doc.indexOf('<script>')
  const body = doc.slice(start + '<script>'.length, doc.indexOf('</script>', start))

  const posted = []
  const listeners = {}
  const fakeConsole = { log: vi.fn(), info: vi.fn(), warn: vi.fn(), error: vi.fn(), debug: vi.fn() }
  const fakeWindow = {
    addEventListener: (type, fn) => { listeners[type] = fn },
  }
  const fakeParent = { postMessage: (msg) => posted.push(msg) }

  // Keep handles to the pre-shim spies: the bridge replaces console[level] with
  // a wrapper, so reading them afterwards would return the wrapper instead.
  const originals = { ...fakeConsole }

  new Function('parent', 'console', 'window', body)(fakeParent, fakeConsole, fakeWindow)

  return { posted, listeners, fakeConsole, originals }
}

const DOC = () => composeHtmlPreview({ 'index.html': '<h1>Hi</h1>' })

describe('preview console bridge (executed)', () => {
  let bridge
  beforeEach(() => { bridge = runBridge(DOC()) })

  it('forwards console.log to the parent with the right message type', () => {
    bridge.fakeConsole.log('hello', 'world')
    expect(bridge.posted).toHaveLength(1)
    expect(bridge.posted[0].type).toBe(PREVIEW_LOG_TYPE)
    expect(bridge.posted[0].level).toBe('log')
    expect(bridge.posted[0].text).toBe('hello world')
  })

  it('preserves each console level', () => {
    bridge.fakeConsole.warn('w')
    bridge.fakeConsole.error('e')
    expect(bridge.posted.map((p) => p.level)).toEqual(['warn', 'error'])
  })

  it('serialises objects rather than posting [object Object]', () => {
    bridge.fakeConsole.log({ a: 1 })
    expect(bridge.posted[0].text).toBe('{"a":1}')
  })

  it('still calls through to the original console so devtools keeps working', () => {
    bridge.fakeConsole.log('x')
    expect(bridge.originals.log).toHaveBeenCalledWith('x')
  })

  it('forwards uncaught errors', () => {
    bridge.listeners.error({ message: 'boom', filename: 'index.html', lineno: 3 })
    expect(bridge.posted[0].level).toBe('error')
    expect(bridge.posted[0].text).toContain('boom')
    expect(bridge.posted[0].text).toContain('index.html:3')
  })

  it('forwards unhandled promise rejections', () => {
    bridge.listeners.unhandledrejection({ reason: new Error('nope') })
    expect(bridge.posted[0].level).toBe('error')
    expect(bridge.posted[0].text).toContain('nope')
  })

  it('stops posting after the cap so a runaway loop cannot flood the parent', () => {
    for (let i = 0; i < 5000; i += 1) bridge.fakeConsole.log(i)
    expect(bridge.posted.length).toBeLessThanOrEqual(200)
    expect(bridge.posted[bridge.posted.length - 1].text).toContain('suppressed')
  })

  it('truncates a single enormous message', () => {
    bridge.fakeConsole.log('x'.repeat(100000))
    expect(bridge.posted[0].text.length).toBeLessThanOrEqual(2000)
  })

  it('survives a value that cannot be stringified', () => {
    const circular = {}
    circular.self = circular
    expect(() => bridge.fakeConsole.log(circular)).not.toThrow()
    expect(bridge.posted).toHaveLength(1)
  })
})
