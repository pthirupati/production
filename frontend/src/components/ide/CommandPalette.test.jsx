// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, fireEvent, cleanup } from '@testing-library/react'
import CommandPalette, { fuzzyScore, rankCommands } from './CommandPalette'

afterEach(cleanup)

describe('fuzzyScore', () => {
  it('matches subsequences like VS Code ("nf" → New File)', () => {
    expect(fuzzyScore('New File', 'nf')).toBeGreaterThanOrEqual(0)
    expect(fuzzyScore('New File', 'newf')).toBeGreaterThanOrEqual(0)
  })

  it('rejects letters that are absent or out of order', () => {
    expect(fuzzyScore('New File', 'zzz')).toBe(-1)
    expect(fuzzyScore('New File', 'fn')).toBe(-1) // wrong order
  })

  it('scores a contiguous prefix better than a scattered subsequence', () => {
    // Both match "nf", but "New File" has it at two word starts while
    // "Rename Confirm" only matches by scattering across the middle.
    const tight = fuzzyScore('New File', 'nf')
    const loose = fuzzyScore('Rename Confirm', 'nf')
    expect(tight).toBeGreaterThanOrEqual(0)
    expect(loose).toBeGreaterThanOrEqual(0)
    expect(tight).toBeLessThan(loose)
  })

  it('treats an empty query as matching everything', () => {
    expect(fuzzyScore('anything', '')).toBe(0)
  })
})

describe('rankCommands', () => {
  const cmds = [
    { id: 'a', label: 'Run', group: 'Run' },
    { id: 'b', label: 'Check Solution', group: 'Run' },
    { id: 'c', label: 'New File', group: 'File' },
    { id: 'd', label: 'Open HTML Preview', group: 'View', hidden: true },
  ]

  it('filters to matches and drops hidden commands', () => {
    expect(rankCommands(cmds, '').map((c) => c.id)).toEqual(['a', 'b', 'c'])
    expect(rankCommands(cmds, 'preview')).toEqual([])
  })

  it('ranks the best match first', () => {
    expect(rankCommands(cmds, 'new file')[0].id).toBe('c')
  })
})

describe('CommandPalette', () => {
  const makeCmds = (over = {}) => [
    { id: 'run', label: 'Run', run: vi.fn(), ...over.run },
    { id: 'newfile', label: 'New File', disabled: true, run: vi.fn(), ...over.newfile },
  ]

  it('renders nothing when closed', () => {
    const { container } = render(<CommandPalette open={false} commands={makeCmds()} onClose={vi.fn()} />)
    expect(container.firstChild).toBeNull()
  })

  it('runs a command on click and closes', () => {
    const cmds = makeCmds()
    const onClose = vi.fn()
    render(<CommandPalette open commands={cmds} onClose={onClose} />)
    fireEvent.click(screen.getByText('Run'))
    expect(cmds[0].run).toHaveBeenCalledTimes(1)
    expect(onClose).toHaveBeenCalled()
  })

  it('NEVER runs a disabled command', () => {
    // The guard that matters: toolbar buttons are disabled while a lab is
    // solved, and the palette must not become a bypass for that.
    const cmds = makeCmds()
    render(<CommandPalette open commands={cmds} onClose={vi.fn()} />)
    fireEvent.click(screen.getByText('New File'))
    expect(cmds[1].run).not.toHaveBeenCalled()
  })

  it('does not run a disabled command via keyboard Enter either', () => {
    const cmds = [{ id: 'x', label: 'Danger', disabled: true, run: vi.fn() }]
    render(<CommandPalette open commands={cmds} onClose={vi.fn()} />)
    const input = screen.getByLabelText('Command')
    fireEvent.keyDown(input, { key: 'Enter' })
    expect(cmds[0].run).not.toHaveBeenCalled()
  })

  it('filters as the user types', () => {
    render(<CommandPalette open commands={makeCmds()} onClose={vi.fn()} />)
    fireEvent.change(screen.getByLabelText('Command'), { target: { value: 'run' } })
    expect(screen.queryByText('New File')).toBeNull()
    expect(screen.getByText('Run')).toBeTruthy()
  })

  it('runs the arrow-selected command on Enter', () => {
    const cmds = [
      { id: 'a', label: 'Alpha', run: vi.fn() },
      { id: 'b', label: 'Beta', run: vi.fn() },
    ]
    render(<CommandPalette open commands={cmds} onClose={vi.fn()} />)
    const input = screen.getByLabelText('Command')
    fireEvent.keyDown(input, { key: 'ArrowDown' })
    fireEvent.keyDown(input, { key: 'Enter' })
    expect(cmds[1].run).toHaveBeenCalledTimes(1)
    expect(cmds[0].run).not.toHaveBeenCalled()
  })

  it('closes on Escape without running anything', () => {
    const cmds = makeCmds()
    const onClose = vi.fn()
    render(<CommandPalette open commands={cmds} onClose={onClose} />)
    fireEvent.keyDown(screen.getByLabelText('Command'), { key: 'Escape' })
    expect(onClose).toHaveBeenCalled()
    expect(cmds[0].run).not.toHaveBeenCalled()
  })

  it('reports when nothing matches', () => {
    render(<CommandPalette open commands={makeCmds()} onClose={vi.fn()} />)
    fireEvent.change(screen.getByLabelText('Command'), { target: { value: 'zzzz' } })
    expect(screen.getByText('No matching commands.')).toBeTruthy()
  })
})
