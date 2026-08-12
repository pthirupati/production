import { describe, expect, it } from 'vitest'
import { promises as fs } from 'fs'
import { applyAuthHeaders, responsePreviewSrcDoc, mergeApiClientDrafts } from './IdeApiClientPanel'
import { nextZoom, prevZoom, PREVIEW_ZOOM_STEPS, formatInspectHit, inspectOverlayStyle } from './HtmlPreviewPane'

describe('mergeApiClientDrafts', () => {
  it('prefers newer ts', () => {
    expect(mergeApiClientDrafts({ url: '/a', ts: 1 }, { url: '/b', ts: 2 }).url).toBe('/b')
    expect(mergeApiClientDrafts({ url: '/a', ts: 5 }, { url: '/b', ts: 2 }).url).toBe('/a')
    expect(mergeApiClientDrafts(null, { url: '/s' }).url).toBe('/s')
  })
})

describe('applyAuthHeaders', () => {
  it('injects Bearer without clobbering explicit Authorization', () => {
    expect(applyAuthHeaders({}, { type: 'bearer', token: 'abc' }).Authorization)
      .toBe('Bearer abc')
    expect(
      applyAuthHeaders({ Authorization: 'Bearer keep' }, { type: 'bearer', token: 'abc' })
        .Authorization,
    ).toBe('Bearer keep')
  })

  it('injects Basic and API key headers', () => {
    const basic = applyAuthHeaders({}, { type: 'basic', username: 'u', password: 'p' })
    expect(basic.Authorization).toMatch(/^Basic /)
    const key = applyAuthHeaders({}, { type: 'apikey', key: 'X-API-Key', value: 'k1' })
    expect(key['X-API-Key']).toBe('k1')
  })
})

describe('responsePreviewSrcDoc', () => {
  it('passes HTML through and wraps JSON', () => {
    expect(responsePreviewSrcDoc({
      headers: { 'content-type': 'text/html' },
      body_text: '<h1>ok</h1>',
    })).toContain('<h1>ok</h1>')
    const wrapped = responsePreviewSrcDoc({ body: { a: 1 } })
    expect(wrapped).toContain('<pre')
    expect(wrapped).toContain('"a"')
  })
})

describe('JsonTreeNode', () => {
  it('is exported and wired into Pretty tab', async () => {
    const { JsonTreeNode } = await import('./IdeApiClientPanel')
    expect(typeof JsonTreeNode).toBe('function')
    const src = await fs.readFile(new URL('./IdeApiClientPanel.jsx', import.meta.url), 'utf8')
    expect(src).toContain('data-testid="api-json-tree"')
    expect(src).toContain('JsonTreeNode')
  })
})

describe('preview zoom helpers', () => {
  it('steps within PREVIEW_ZOOM_STEPS', () => {
    expect(nextZoom(1)).toBe(1.25)
    expect(prevZoom(1)).toBe(0.75)
    expect(nextZoom(PREVIEW_ZOOM_STEPS[PREVIEW_ZOOM_STEPS.length - 1])).toBe(
      PREVIEW_ZOOM_STEPS[PREVIEW_ZOOM_STEPS.length - 1],
    )
    expect(prevZoom(PREVIEW_ZOOM_STEPS[0])).toBe(PREVIEW_ZOOM_STEPS[0])
  })

  it('formatInspectHit summarizes tag/id/class/size', () => {
    expect(formatInspectHit({
      tag: 'button', id: 'go', className: 'primary big', w: 80, h: 32,
    })).toBe('button #go .primary.big 80×32')
  })

  it('inspectOverlayStyle positions the highlight box', () => {
    const s = inspectOverlayStyle({ left: 10, top: 20, w: 40, h: 15 }, 2)
    expect(s.left).toBe(20)
    expect(s.top).toBe(40)
    expect(s.width).toBe(80)
    expect(s.height).toBe(30)
  })
})

describe('IdeApiClientPanel Auth + Preview', () => {
  it('exposes Auth type control, applyAuthHeaders, and preview tab', async () => {
    const src = await fs.readFile(new URL('./IdeApiClientPanel.jsx', import.meta.url), 'utf8')
    expect(src).toContain('data-testid="api-auth"')
    expect(src).toContain('Auth type')
    expect(src).toContain('applyAuthHeaders')
    expect(src).toContain('Bearer Token')
    expect(src).toContain('data-testid="api-response-preview"')
    expect(src).toContain('responsePreviewSrcDoc')
  })
})

describe('HtmlPreviewPane zoom + inspect', () => {
  it('wires zoom and inspect controls', async () => {
    const src = await fs.readFile(new URL('./HtmlPreviewPane.jsx', import.meta.url), 'utf8')
    expect(src).toContain('data-testid="preview-zoom"')
    expect(src).toContain('Zoom in')
    expect(src).toContain('nextZoom')
    expect(src).toContain('data-testid="preview-inspect"')
    expect(src).toContain('data-testid="preview-inspect-overlay"')
    expect(src).toContain('formatInspectHit')
    expect(src).toContain('Inspect element')
  })
})
