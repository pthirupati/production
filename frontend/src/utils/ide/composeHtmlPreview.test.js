// @vitest-environment node
import { describe, it, expect } from 'vitest'
import { composeHtmlPreview, hasHtmlPreview, editorLanguageForPath, preferredHtmlPath, resolvePreviewRef, PREVIEW_LOG_TYPE } from './composeHtmlPreview'

describe('composeHtmlPreview', () => {
  it('detects html projects', () => {
    expect(hasHtmlPreview({ 'index.html': '<h1>Hi</h1>' })).toBe(true)
    expect(hasHtmlPreview({ 'solution.js': 'x=1' }, 'javascript')).toBe(false)
    expect(hasHtmlPreview({}, 'html')).toBe(true)
  })

  it('inlines css and browser js into index.html', () => {
    const doc = composeHtmlPreview({
      'index.html': '<!DOCTYPE html><html><head></head><body><h1 id="t">Hi</h1></body></html>',
      'styles.css': 'h1 { color: red; }',
      'app.js': 'document.getElementById("t").textContent = "Ok";',
      'solution.js': 'function unused() {}',
    })
    expect(doc).toContain('h1 { color: red; }')
    expect(doc).toContain('document.getElementById')
    expect(doc).not.toContain('function unused')
  })

  it('picks language from path', () => {
    expect(editorLanguageForPath('src/app.js', 'python')).toBe('javascript')
    expect(editorLanguageForPath('index.html', 'javascript')).toBe('html')
    expect(editorLanguageForPath('styles.css')).toBe('css')
    expect(editorLanguageForPath('main.py')).toBe('python')
  })
})

describe('preferredHtmlPath — the file an HTML lab should open on', () => {
  // The exact shape every one of the 150 scenarios/html labs ships: the declared
  // entrypoint is a READ-ONLY grader harness whose own first line says
  // "Keep this file; edit index.html and styles.css instead."
  const HTML_LAB_FILES = {
    'index.html': '<!DOCTYPE html><html lang="en"><body></body></html>',
    'styles.css': 'body { font-family: system-ui; }',
    'solution.js': '// Grader harness — PAGE_HTML / PAGE_CSS are injected server-side.',
  }

  it('opens index.html, not the readonly solution.js entrypoint', () => {
    expect(preferredHtmlPath(HTML_LAB_FILES)).toBe('index.html')
  })

  it('treats the real lab shape as previewable', () => {
    expect(hasHtmlPreview(HTML_LAB_FILES, 'javascript')).toBe(true)
  })

  it('gives the opened file html syntax, not the spec-level javascript', () => {
    // spec.language is "javascript" for these labs because the GRADER runs JS;
    // the editor must still highlight the file the learner is editing as HTML.
    expect(editorLanguageForPath('index.html', 'javascript')).toBe('html')
    expect(editorLanguageForPath('styles.css', 'javascript')).toBe('css')
  })

  it('prefers index.html over other html files regardless of key order', () => {
    expect(preferredHtmlPath({ 'about.html': '', 'index.html': '' })).toBe('index.html')
    expect(preferredHtmlPath({ 'index.html': '', 'about.html': '' })).toBe('index.html')
  })

  it('falls back to the only html file when there is no index', () => {
    expect(preferredHtmlPath({ 'page.html': '', 'solution.js': '' })).toBe('page.html')
  })

  it('returns empty string for a non-html project so callers can skip', () => {
    expect(preferredHtmlPath({ 'solution.py': 'x=1' })).toBe('')
    expect(preferredHtmlPath({})).toBe('')
  })

  it('agrees with the document the preview actually renders', () => {
    // If these ever diverge the learner edits one file and previews another.
    const doc = composeHtmlPreview(HTML_LAB_FILES)
    expect(doc).toContain('lang="en"')
    expect(doc).toContain('font-family: system-ui')
  })

  it('still renders the lab content once the console bridge is injected', () => {
    // Guards the 155 HTML labs against a shim that blanks the preview.
    const doc = composeHtmlPreview(HTML_LAB_FILES)
    expect(doc).toContain(PREVIEW_LOG_TYPE)
    expect(doc).toContain('lang="en"')
    expect(doc).toContain('font-family: system-ui')
  })
})

describe('relative <link>/<script src> resolution (opaque-origin srcDoc)', () => {
  // The exact index.html shipped by all 40 scenarios/html labs that link a sheet.
  const LINKED = [
    '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8" />',
    '<title>Lab</title><link rel="stylesheet" href="styles.css" /></head>',
    '<body><p>Welcome</p></body></html>',
  ].join('')

  it('inlines a linked stylesheet instead of leaving a ref that 404s', () => {
    const doc = composeHtmlPreview({
      'index.html': LINKED,
      'styles.css': 'body { font-family: system-ui; }',
      'solution.js': '// harness',
    })
    expect(doc).not.toMatch(/<link[^>]*href="styles\.css"/i)
    expect(doc).toContain('font-family: system-ui')
  })

  it('inlines the sheet where the <link> was, not appended after it', () => {
    // Cascade order is semantics: a sheet linked in <head> must not jump ahead
    // of or behind an inline <style> the author wrote after it.
    const doc = composeHtmlPreview({
      'index.html': '<html><head><link rel="stylesheet" href="a.css" /><style>p{color:blue}</style></head><body></body></html>',
      'a.css': 'p{color:red}',
    })
    expect(doc.indexOf('p{color:red}')).toBeLessThan(doc.indexOf('p{color:blue}'))
  })

  it('only inlines the sheets the document actually links', () => {
    // theme-dark and theme-light must not both apply.
    const doc = composeHtmlPreview({
      'index.html': '<html><head><link rel="stylesheet" href="theme-dark.css" /></head><body></body></html>',
      'theme-dark.css': 'body{background:#000}',
      'theme-light.css': 'body{background:#fff}',
    })
    expect(doc).toContain('body{background:#000}')
    expect(doc).not.toContain('body{background:#fff}')
  })

  it('still inlines every stylesheet when the document links none', () => {
    // 110 of the 150 html labs never emit a <link> — the composer is the only
    // reason their CSS applies at all. Removing this fallback blanks them.
    const doc = composeHtmlPreview({
      'index.html': '<html><head></head><body><p>Hi</p></body></html>',
      'styles.css': 'p{color:green}',
    })
    expect(doc).toContain('p{color:green}')
  })

  it('inlines <script src> in place and does not also append a duplicate copy', () => {
    // Double execution is the trap: a side-effectful lab script would run twice
    // and produce output that looks like a learner bug.
    const doc = composeHtmlPreview({
      'index.html': '<html><head></head><body><script src="app.js"></script></body></html>',
      'app.js': 'window.__hits = (window.__hits || 0) + 1;',
    })
    const hits = doc.split('window.__hits = (window.__hits || 0) + 1;').length - 1
    expect(hits).toBe(1)
    expect(doc).not.toMatch(/<script[^>]*\ssrc="app\.js"/i)
  })

  it('keeps a head <script src> in the head rather than moving it to end-of-body', () => {
    const doc = composeHtmlPreview({
      'index.html': '<html><head><script src="boot.js"></script></head><body><p>Hi</p></body></html>',
      'boot.js': 'var BOOTED = 1;',
    })
    expect(doc.indexOf('var BOOTED = 1;')).toBeLessThan(doc.indexOf('<p>Hi</p>'))
  })

  it('strips a dangling <script src> so the iframe cannot 404 on it', () => {
    // scenarios/html/academy-html-005-production-performance ships exactly this:
    // <script src="app.js"> with no app.js anywhere in the file map.
    const doc = composeHtmlPreview({
      'index.html': '<html><head></head><body><img src="hero.jpg" alt="Hero" /><script src="app.js"></script></body></html>',
      'styles.css': 'img { max-width: 100%; }',
    })
    expect(doc).not.toMatch(/src="app\.js"/i)
  })

  it('strips a dangling <link href> too', () => {
    const doc = composeHtmlPreview({
      'index.html': '<html><head><link rel="stylesheet" href="missing.css" /></head><body></body></html>',
    })
    expect(doc).not.toContain('missing.css')
  })

  it('leaves external CDN refs alone', () => {
    const doc = composeHtmlPreview({
      'index.html': '<html><head><link rel="stylesheet" href="https://cdn.example/x.css" /></head><body><script src="//cdn.example/y.js"></script></body></html>',
    })
    expect(doc).toContain('https://cdn.example/x.css')
    expect(doc).toContain('//cdn.example/y.js')
  })

  it('leaves author-written inline scripts untouched', () => {
    const doc = composeHtmlPreview({
      'index.html': '<html><head></head><body><script>var INLINE = 1;</script></body></html>',
    })
    expect(doc).toContain('var INLINE = 1;')
  })

  it('resolves ./ and root-relative and same-directory refs', () => {
    expect(resolvePreviewRef({ 'styles.css': '' }, './styles.css')).toBe('styles.css')
    expect(resolvePreviewRef({ 'styles.css': '' }, '/styles.css')).toBe('styles.css')
    expect(resolvePreviewRef({ 'src/a.css': '' }, 'a.css', 'src/index.html')).toBe('src/a.css')
    expect(resolvePreviewRef({ 'styles.css': '' }, 'styles.css?v=2')).toBe('styles.css')
    expect(resolvePreviewRef({ 'styles.css': '' }, 'https://x/styles.css')).toBe('')
    expect(resolvePreviewRef({ 'styles.css': '' }, 'nope.css')).toBe('')
  })

  it('does not guess when a basename is ambiguous', () => {
    expect(resolvePreviewRef({ 'a/x.css': '', 'b/x.css': '' }, 'x.css')).toBe('')
  })

  it('renders the verbatim perf lab, whose <script src> names a file that does not exist', () => {
    // Copied byte-for-byte from scenarios/html/academy-html-005-production-performance
    // (and its 9 siblings). There is no app.js in the file map at all.
    const doc = composeHtmlPreview({
      'index.html': '<!DOCTYPE html>\n<html lang="en"><head><meta charset="utf-8" /><title>Perf</title><link rel="stylesheet" href="styles.css" /></head><body>\n  <img src="hero.jpg" alt="Hero" />\n  <script src="app.js"></script>\n  <!-- TODO: lazy-load the image; defer the script -->\n</body></html>\n',
      'styles.css': 'img { max-width: 100%; }\n',
      'solution.js': '// Grader harness',
    })
    expect(doc).toContain('img { max-width: 100%; }')
    expect(doc).toContain('alt="Hero"')
    // Neither the sheet ref nor the missing script ref survives to fire a 404.
    expect(doc).not.toMatch(/<link[^>]*href="styles\.css"/i)
    expect(doc).not.toMatch(/<script[^>]*\ssrc="app\.js"/i)
    // The grader harness is still excluded from the preview.
    expect(doc).not.toContain('Grader harness')
  })

  it('still runs the console bridge before an inlined <script src>', () => {
    const doc = composeHtmlPreview({
      'index.html': '<html><head><script src="boot.js"></script></head><body></body></html>',
      'boot.js': 'console.log("from learner")',
    })
    expect(doc.indexOf(PREVIEW_LOG_TYPE)).toBeLessThan(doc.indexOf('from learner'))
  })
})

describe('preview console bridge', () => {
  const shimOf = (doc) => doc.slice(doc.indexOf('<script>'), doc.indexOf('</script>') + 9)

  it('injects the bridge for a full document with a head', () => {
    const doc = composeHtmlPreview({
      'index.html': '<!DOCTYPE html><html><head><title>t</title></head><body><h1>Hi</h1></body></html>',
    })
    expect(doc).toContain(PREVIEW_LOG_TYPE)
    // Content survives.
    expect(doc).toContain('<h1>Hi</h1>')
    expect(doc).toContain('<title>t</title>')
  })

  it('injects for a body-only document', () => {
    const doc = composeHtmlPreview({ 'index.html': '<body><h1>Hi</h1></body>' })
    expect(doc).toContain(PREVIEW_LOG_TYPE)
    expect(doc).toContain('<h1>Hi</h1>')
  })

  it('injects for a bare fragment with neither head nor body', () => {
    const doc = composeHtmlPreview({ 'index.html': '<h1>Hi</h1>' })
    expect(doc).toContain(PREVIEW_LOG_TYPE)
    expect(doc).toContain('<h1>Hi</h1>')
  })

  it('runs before the learner js so their console output is captured', () => {
    const doc = composeHtmlPreview({
      'index.html': '<!DOCTYPE html><html><head></head><body></body></html>',
      'app.js': 'console.log("from learner")',
    })
    expect(doc.indexOf(PREVIEW_LOG_TYPE)).toBeLessThan(doc.indexOf('from learner'))
  })

  it('caps output so a runaway loop cannot flood the parent', () => {
    const shim = shimOf(composeHtmlPreview({ 'index.html': '<h1>Hi</h1>' }))
    expect(shim).toMatch(/MAX_MESSAGES/)
    expect(shim).toMatch(/if \(sent >= MAX_MESSAGES\) return/)
  })

  it('wraps itself in try/catch so it can never break the preview', () => {
    const shim = shimOf(composeHtmlPreview({ 'index.html': '<h1>Hi</h1>' }))
    expect(shim).toContain('try {')
    expect(shim).toContain('catch')
  })

  it('reports uncaught errors and promise rejections, not just console calls', () => {
    const shim = shimOf(composeHtmlPreview({ 'index.html': '<h1>Hi</h1>' }))
    expect(shim).toContain("addEventListener('error'")
    expect(shim).toContain("addEventListener('unhandledrejection'")
  })

  it('can be disabled without changing the rendered content', () => {
    const files = { 'index.html': '<!DOCTYPE html><html><head></head><body><h1>Hi</h1></body></html>' }
    const doc = composeHtmlPreview(files, { consoleBridge: false })
    expect(doc).not.toContain(PREVIEW_LOG_TYPE)
    expect(doc).toContain('<h1>Hi</h1>')
  })
})
