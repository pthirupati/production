import { describe, expect, it, vi } from 'vitest'
import { render, waitFor } from '@testing-library/react'
import IdeLocalTerminal from './IdeLocalTerminal'

vi.mock('@xterm/xterm', () => {
  class FakeTerminal {
    constructor() {
      this.lines = []
      this._onData = null
    }
    open() {}
    writeln(s) { this.lines.push(String(s)) }
    write(s) { this.lines.push(String(s)) }
    clear() { this.lines = [] }
    onData(cb) { this._onData = cb }
    dispose() {}
  }
  return { Terminal: FakeTerminal }
})

vi.mock('@xterm/xterm/css/xterm.css', () => ({}))

describe('IdeLocalTerminal', () => {
  it('mounts and exposes writeln', async () => {
    const ref = { current: null }
    render(<IdeLocalTerminal ref={(r) => { ref.current = r }} />)
    await waitFor(() => expect(ref.current).toBeTruthy())
    expect(() => ref.current.writeln('hello from run')).not.toThrow()
  })
})
