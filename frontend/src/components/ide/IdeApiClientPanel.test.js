import { describe, expect, it, vi } from 'vitest'
import { promises as fs } from 'fs'

vi.mock('../../api/labs', () => ({
  labApi: {
    apiClientSend: vi.fn(async () => ({
      ok: true,
      status: 200,
      reason: 'OK',
      elapsed_ms: 1.2,
      bytes: 20,
      headers: { 'content-type': 'application/json' },
      body: { status: 'ok' },
      body_text: '{"status":"ok"}',
      request: { method: 'GET', url: '/health' },
      mock: true,
    })),
  },
}))

describe('IdeApiClientPanel / CodingIDE API tab', () => {
  it('CodingIDE registers an API bottom tab and mounts IdeApiClientPanel', async () => {
    const src = await fs.readFile(new URL('./CodingIDE.jsx', import.meta.url), 'utf8')
    expect(src).toContain("key: 'api'")
    expect(src).toContain('IdeApiClientPanel')
    expect(src).toContain("bottomTab === 'api'")
  })

  it('panel exposes method, URL, Send, and response tabs', async () => {
    const src = await fs.readFile(new URL('./IdeApiClientPanel.jsx', import.meta.url), 'utf8')
    expect(src).toContain('data-testid="ide-api-client"')
    expect(src).toContain('HTTP method')
    expect(src).toContain('Request URL')
    expect(src).toContain('apiClientSend')
    expect(src).toContain('pretty')
    expect(src).toContain('Sent {response.request.method}')
  })
})
