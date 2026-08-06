// @vitest-environment jsdom
import { describe, it, expect, beforeEach, vi } from 'vitest'

// zustand's persist middleware (themeStore) grabs localStorage at module
// evaluation time, and jsdom 29 does not provide it without --localstorage-file.
vi.hoisted(() => {
  const store = new Map()
  globalThis.localStorage = {
    getItem: (k) => (store.has(String(k)) ? store.get(String(k)) : null),
    setItem: (k, v) => { store.set(String(k), String(v)) },
    removeItem: (k) => { store.delete(String(k)) },
    clear: () => store.clear(),
  }
})

import { render, cleanup } from '@testing-library/react'
import { undo } from '@codemirror/commands'
import { createRef } from 'react'
import CodeEditor from './CodeEditor'

// CodeMirror needs a couple of layout APIs jsdom does not implement.
beforeEach(() => {
  cleanup()
  if (!Range.prototype.getClientRects) {
    Range.prototype.getClientRects = () => ({ length: 0, item: () => null, [Symbol.iterator]: function* () {} })
    Range.prototype.getBoundingClientRect = () => ({ x: 0, y: 0, top: 0, left: 0, right: 0, bottom: 0, width: 0, height: 0 })
  }
})

function typeInto(view, text) {
  view.dispatch({
    changes: { from: view.state.doc.length, to: view.state.doc.length, insert: text },
  })
}

describe('CodeEditor per-path EditorState', () => {
  it('keeps undo history when switching tabs and coming back', () => {
    const files = { 'a.py': 'a = 1\n', 'b.py': 'b = 2\n' }
    const ref = createRef()
    const onChange = vi.fn()

    const { rerender } = render(
      <CodeEditor ref={ref} docPath="a.py" value={files['a.py']} onChange={onChange} language="python" />,
    )
    const view = ref.current.getView()
    expect(view).toBeTruthy()

    // Edit file A, then let the parent's controlled value catch up.
    typeInto(view, 'a = 2\n')
    files['a.py'] = view.state.doc.toString()
    expect(files['a.py']).toBe('a = 1\na = 2\n')

    // Switch to B, then back to A — the old key={activePath} remount happened here.
    rerender(<CodeEditor ref={ref} docPath="b.py" value={files['b.py']} onChange={onChange} language="python" />)
    expect(ref.current.getValue()).toBe('b = 2\n')

    rerender(<CodeEditor ref={ref} docPath="a.py" value={files['a.py']} onChange={onChange} language="python" />)
    const back = ref.current.getView()
    expect(back.state.doc.toString()).toBe('a = 1\na = 2\n')

    // The real assertion: undo still knows about the edit made before the switch.
    const didUndo = undo(back)
    expect(didUndo).toBe(true)
    expect(back.state.doc.toString()).toBe('a = 1\n')
  })

  it('shows the incoming file, never the outgoing one', () => {
    const ref = createRef()
    const { rerender } = render(
      <CodeEditor ref={ref} docPath="a.py" value={"a = 1\n"} onChange={() => {}} language="python" />,
    )
    rerender(<CodeEditor ref={ref} docPath="b.py" value={"b = 2\n"} onChange={() => {}} language="python" />)
    expect(ref.current.getValue()).toBe('b = 2\n')
  })

  it('prefers the incoming value when a cached state is stale', () => {
    const ref = createRef()
    const { rerender } = render(
      <CodeEditor ref={ref} docPath="a.py" value={"a = 1\n"} onChange={() => {}} language="python" />,
    )
    rerender(<CodeEditor ref={ref} docPath="b.py" value={"b = 2\n"} onChange={() => {}} language="python" />)

    // a.py changed while closed (draft restore / Refresh / rename).
    rerender(<CodeEditor ref={ref} docPath="a.py" value={"a = 999\n"} onChange={() => {}} language="python" />)
    expect(ref.current.getValue()).toBe('a = 999\n')
  })

  it('does not report a change against the newly opened path during a swap', () => {
    const onChange = vi.fn()
    const ref = createRef()
    const { rerender } = render(
      <CodeEditor ref={ref} docPath="a.py" value={"a = 1\n"} onChange={onChange} language="python" />,
    )
    onChange.mockClear()

    // Swapping documents must not look like the learner typed file A's contents
    // into file B — that would autosave the wrong content to the wrong path.
    rerender(<CodeEditor ref={ref} docPath="b.py" value={"b = 2\n"} onChange={onChange} language="python" />)
    expect(onChange).not.toHaveBeenCalled()
  })
})
