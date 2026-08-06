// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach } from 'vitest'
import { renderHook, waitFor, act } from '@testing-library/react'

const getMock = vi.fn()
vi.mock('../api/client', () => ({
  default: { get: (...args) => getMock(...args) },
}))

const { useFetch } = await import('./useFetch')

afterEach(() => { getMock.mockReset() })

describe('useFetch', () => {
  it('exposes loading then data', async () => {
    getMock.mockResolvedValue({ data: { id: 1 } })
    const { result } = renderHook(() => useFetch('/labs/'))
    expect(result.current.loading).toBe(true)
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.data).toEqual({ id: 1 })
    expect(result.current.error).toBeNull()
  })

  it('records an error and stops loading', async () => {
    getMock.mockRejectedValue(Object.assign(new Error('nope'), { response: { status: 500 } }))
    const { result } = renderHook(() => useFetch('/labs/'))
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.error).toBeTruthy()
    expect(result.current.data).toBeNull()
  })

  it('flags a 403 as forbidden so a page can render an upgrade prompt', async () => {
    getMock.mockRejectedValue(Object.assign(new Error('denied'), { response: { status: 403 } }))
    const { result } = renderHook(() => useFetch('/vmware/sessions/1/'))
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.forbidden).toBe(true)
  })

  it('passes an AbortSignal and aborts it on unmount', async () => {
    getMock.mockImplementation(() => new Promise(() => {})) // never settles
    const { unmount } = renderHook(() => useFetch('/labs/'))
    await waitFor(() => expect(getMock).toHaveBeenCalled())
    const signal = getMock.mock.calls[0][1].signal
    expect(signal).toBeInstanceOf(AbortSignal)
    expect(signal.aborted).toBe(false)
    unmount()
    expect(signal.aborted).toBe(true)
  })

  it('does not set error state when the request was aborted', async () => {
    getMock.mockRejectedValue(Object.assign(new Error('canceled'), { code: 'ERR_CANCELED' }))
    const { result } = renderHook(() => useFetch('/labs/'))
    await waitFor(() => expect(getMock).toHaveBeenCalled())
    // An aborted request is normal navigation, not a failure to show the user.
    await waitFor(() => expect(result.current.error).toBeNull())
  })

  it('skips the request when url is null or enabled is false', async () => {
    const { result } = renderHook(() => useFetch(null))
    expect(getMock).not.toHaveBeenCalled()
    expect(result.current.loading).toBe(false)

    renderHook(() => useFetch('/labs/', { enabled: false }))
    expect(getMock).not.toHaveBeenCalled()
  })

  it('does not refetch when config is an inline object literal', async () => {
    getMock.mockResolvedValue({ data: {} })
    // A naive [config] dep would loop forever: a new object each render.
    const { rerender, result } = renderHook(() => useFetch('/labs/', { config: { params: { page: 1 } } }))
    await waitFor(() => expect(result.current.loading).toBe(false))
    rerender()
    rerender()
    expect(getMock).toHaveBeenCalledTimes(1)
  })

  it('refetch re-issues the request', async () => {
    getMock.mockResolvedValue({ data: { n: 1 } })
    const { result } = renderHook(() => useFetch('/labs/'))
    await waitFor(() => expect(result.current.loading).toBe(false))
    getMock.mockResolvedValue({ data: { n: 2 } })
    await act(async () => { await result.current.refetch() })
    expect(result.current.data).toEqual({ n: 2 })
  })

  it('forwards a per-call timeout from config', async () => {
    getMock.mockResolvedValue({ data: {} })
    const { result } = renderHook(() => useFetch('/progress/', { config: { timeout: 10_000 } }))
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(getMock.mock.calls[0][1].timeout).toBe(10_000)
  })
})
