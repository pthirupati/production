import { describe, expect, it, vi, beforeEach } from 'vitest'
import { runApiClientScripts } from '../../utils/ide/jsRunner'

describe('runApiClientScripts pm shim', () => {
  it('sets env + headers in pre-request and grades response in tests', async () => {
    const pre = await runApiClientScripts({
      preRequest: `
        pm.environment.set('token', 'abc');
        pm.request.headers.add({ key: 'X-Token', value: 'abc' });
      `,
      environment: { host: 'api.local' },
      request: { headers: { Accept: 'application/json' } },
    })
    expect(pre.error).toBe('')
    expect(pre.environment.token).toBe('abc')
    expect(pre.headers['X-Token']).toBe('abc')

    const post = await runApiClientScripts({
      tests: `
        pm.test('status', () => { pm.expect(pm.response.code).to.eql(200); });
        pm.test('body', () => { pm.expect(pm.response.json().status).to.eql('ok'); });
      `,
      response: {
        status: 200,
        elapsed_ms: 3,
        headers: { 'content-type': 'application/json' },
        body: { status: 'ok' },
      },
    })
    expect(post.ok).toBe(true)
    expect(post.results).toHaveLength(2)
    expect(post.results.every((r) => r.passed)).toBe(true)
  })
})
