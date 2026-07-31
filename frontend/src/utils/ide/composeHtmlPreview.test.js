// @vitest-environment node
import { describe, it, expect } from 'vitest'
import { composeHtmlPreview, hasHtmlPreview, editorLanguageForPath } from './composeHtmlPreview'

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
    expect(editorLanguageForPath('index.html', 'javascript')).toBe('markdown')
    expect(editorLanguageForPath('main.py')).toBe('python')
  })
})
