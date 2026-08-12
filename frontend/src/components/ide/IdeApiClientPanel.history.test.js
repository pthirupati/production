import { describe, expect, it } from 'vitest'
import { promises as fs } from 'fs'
import {
  HISTORY_LIMIT,
  apiClientStorageKey,
  loadApiClientDraft,
  pushHistory,
  saveApiClientDraft,
  SEEDED_COLLECTION,
} from './IdeApiClientPanel'

describe('API client env / history persist', () => {
  it('round-trips draft + history ring buffer', () => {
    const store = {
      data: {},
      getItem(k) { return this.data[k] ?? null },
      setItem(k, v) { this.data[k] = String(v) },
    }
    const key = apiClientStorageKey('sess-1')
    expect(key).toContain('api-client')
    saveApiClientDraft('sess-1', {
      method: 'POST',
      url: '/api/v1/echo',
      history: pushHistory([], { method: 'GET', url: '/health', status: 200 }),
    }, store)
    const loaded = loadApiClientDraft('sess-1', store)
    expect(loaded.method).toBe('POST')
    expect(loaded.history).toHaveLength(1)
    expect(loaded.history[0].url).toBe('/health')

    let hist = []
    for (let i = 0; i < 30; i += 1) {
      hist = pushHistory(hist, { method: 'GET', url: `/${i}`, status: 200 })
    }
    expect(hist).toHaveLength(HISTORY_LIMIT)
    expect(SEEDED_COLLECTION.length).toBeGreaterThanOrEqual(2)
  })

  it('panel source wires collection + history', async () => {
    const src = await fs.readFile(new URL('./IdeApiClientPanel.jsx', import.meta.url), 'utf8')
    expect(src).toContain('SEEDED_COLLECTION')
    expect(src).toContain('api-history')
    expect(src).toContain('saveApiClientDraft')
  })
})
