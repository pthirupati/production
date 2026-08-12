// @vitest-environment jsdom
import { describe, it, expect, beforeEach, vi } from 'vitest'

// zustand's persist middleware (themeStore) grabs localStorage at module
// evaluation time, and the node test environment does not provide it.
vi.hoisted(() => {
  const store = new Map()
  globalThis.localStorage = {
    getItem: (k) => (store.has(String(k)) ? store.get(String(k)) : null),
    setItem: (k, v) => { store.set(String(k), String(v)) },
    removeItem: (k) => { store.delete(String(k)) },
    clear: () => store.clear(),
  }
})

import { resolveIsDark } from './CodeEditor'
import { useThemeStore } from '../../store/themeStore'

describe('resolveIsDark', () => {
  it('pins the editor independently of the app theme', () => {
    // The whole point of the item: a dark editor inside a light app, and vice
    // versa. Previously isDark was `appTheme !== 'light'` with no editor input.
    expect(resolveIsDark('dark', 'light')).toBe(true)
    expect(resolveIsDark('light', 'dark')).toBe(false)
  })

  it('follows the app theme when set to auto', () => {
    expect(resolveIsDark('auto', 'dark')).toBe(true)
    expect(resolveIsDark('auto', 'light')).toBe(false)
  })

  it('follows the app theme when the preference is missing', () => {
    // A themeStore payload persisted before editorTheme existed hydrates without
    // the key; falling back to the app theme is what stops a wrong-theme flash.
    expect(resolveIsDark(undefined, 'light')).toBe(false)
    expect(resolveIsDark(undefined, 'dark')).toBe(true)
    expect(resolveIsDark('nonsense', 'light')).toBe(false)
  })
})

describe('themeStore editorTheme', () => {
  beforeEach(() => {
    useThemeStore.setState({ theme: 'dark', editorTheme: 'auto' })
  })

  it('defaults to auto so existing users see no change', () => {
    expect(useThemeStore.getState().editorTheme).toBe('auto')
    expect(useThemeStore.getState().resolvedEditorTheme()).toBe('dark')
  })

  it('resolves auto against the current app theme', () => {
    useThemeStore.getState().setTheme('light')
    expect(useThemeStore.getState().resolvedEditorTheme()).toBe('light')
  })

  it('keeps the editor pinned when the app theme toggles', () => {
    useThemeStore.getState().setEditorTheme('dark')
    useThemeStore.getState().setTheme('light')
    expect(useThemeStore.getState().resolvedEditorTheme()).toBe('dark')
    expect(useThemeStore.getState().theme).toBe('light')
  })

  it('does not touch the document data-theme attribute', () => {
    // Editor theme is editor-only; changing it must not restyle the app chrome.
    const spy = vi.spyOn(document.documentElement, 'setAttribute')
    useThemeStore.getState().setEditorTheme('light')
    expect(spy).not.toHaveBeenCalled()
    spy.mockRestore()
  })
})
