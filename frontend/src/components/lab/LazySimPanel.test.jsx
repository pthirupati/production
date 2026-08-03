// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import LazySimPanel from './LazySimPanel'

vi.mock('../SimErrorBoundary', () => ({
  default: function MockBoundary({ children, autoResetStorageOnError, onResetStorage, name }) {
    return (
      <div
        data-testid="sim-boundary"
        data-name={name}
        data-autoreset={autoResetStorageOnError ? '1' : '0'}
        data-has-reset={onResetStorage ? '1' : '0'}
      >
        {children}
      </div>
    )
  },
}))

vi.mock('./LabSimFallback', () => ({
  default: ({ label }) => <div data-testid="fallback">{label}</div>,
}))

function DummySim() {
  return <div data-testid="dummy-sim">ok</div>
}

describe('LazySimPanel AWS reset props', () => {
  beforeEach(() => cleanup())
  afterEach(() => cleanup())

  it('forwards autoReset + onResetStorage for companion AWS overlays', async () => {
    const onResetStorage = vi.fn()
    render(
      <LazySimPanel
        Sim={DummySim}
        name="aws"
        label="AWS Console"
        autoResetStorageOnError
        onResetStorage={onResetStorage}
      />,
    )
    await waitFor(() => expect(screen.getByTestId('dummy-sim')).toBeTruthy())
    const boundary = screen.getByTestId('sim-boundary')
    expect(boundary.getAttribute('data-name')).toBe('aws')
    expect(boundary.getAttribute('data-autoreset')).toBe('1')
    expect(boundary.getAttribute('data-has-reset')).toBe('1')
  })

  it('defaults autoReset off when not an AWS companion', async () => {
    render(<LazySimPanel Sim={DummySim} label="nmap" />)
    await waitFor(() => expect(screen.getByTestId('dummy-sim')).toBeTruthy())
    const boundary = screen.getByTestId('sim-boundary')
    expect(boundary.getAttribute('data-autoreset')).toBe('0')
    expect(boundary.getAttribute('data-has-reset')).toBe('0')
  })
})
