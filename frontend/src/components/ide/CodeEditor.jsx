import { useEffect, useRef } from 'react'
import { EditorState, Compartment } from '@codemirror/state'
import { EditorView, keymap, lineNumbers, highlightActiveLine, highlightActiveLineGutter } from '@codemirror/view'
import { defaultKeymap, history, historyKeymap, indentWithTab } from '@codemirror/commands'
import { indentUnit, indentOnInput, bracketMatching, foldGutter } from '@codemirror/language'
import { python } from '@codemirror/lang-python'
import { javascript } from '@codemirror/lang-javascript'
import { oneDark } from '@codemirror/theme-one-dark'
import { useThemeStore } from '../../store/themeStore'

/**
 * Map a scenario language to the matching CodeMirror language extension.
 * Falls back to no language extension (plain text) for anything unknown so the
 * editor never crashes on an unexpected language.
 */
function languageExtension(language) {
  const lang = (language || '').toLowerCase()
  if (lang === 'python') return python()
  if (lang === 'javascript' || lang === 'js' || lang === 'node' || lang === 'nodejs') {
    return javascript()
  }
  return []
}

// A light editor theme so the IDE reads well in the app's light mode. Dark mode
// uses the bundled oneDark theme. Colours are intentionally neutral so the
// editor blends with surrounding surface tokens.
const lightTheme = EditorView.theme({
  '&': { backgroundColor: '#ffffff', color: '#1e293b' },
  '.cm-gutters': { backgroundColor: '#f8fafc', color: '#94a3b8', border: 'none' },
  '.cm-activeLineGutter': { backgroundColor: '#eef2f7' },
  '.cm-activeLine': { backgroundColor: '#f1f5f9' },
  '.cm-content': { caretColor: '#0e7490' },
  '&.cm-focused .cm-cursor': { borderLeftColor: '#0e7490' },
  '.cm-selectionBackground, &.cm-focused .cm-selectionBackground': { backgroundColor: '#cbd5e1' },
}, { dark: false })

/**
 * Reusable CodeMirror 6 editor. Controlled-ish: `value` seeds the document and
 * pushes external updates in; `onChange` reports edits back to the parent.
 *
 * Props:
 *   value       current document text
 *   onChange    (text) => void
 *   language    'python' | 'javascript' | ...
 *   readOnly    boolean
 *   onRun       optional () => void bound to Ctrl/Cmd-Enter
 */
export default function CodeEditor({ value = '', onChange, language = 'python', readOnly = false, onRun }) {
  const hostRef = useRef(null)
  const viewRef = useRef(null)
  const onChangeRef = useRef(onChange)
  const onRunRef = useRef(onRun)
  const langCompartment = useRef(new Compartment())
  const themeCompartment = useRef(new Compartment())
  const readOnlyCompartment = useRef(new Compartment())

  const theme = useThemeStore((s) => s.theme)
  const isDark = theme !== 'light'

  // Keep latest callbacks without recreating the editor on every render.
  useEffect(() => { onChangeRef.current = onChange }, [onChange])
  useEffect(() => { onRunRef.current = onRun }, [onRun])

  // Create the editor once.
  useEffect(() => {
    if (!hostRef.current) return

    const runKeymap = keymap.of([
      {
        key: 'Mod-Enter',
        run: () => { onRunRef.current?.(); return true },
      },
    ])

    const updateListener = EditorView.updateListener.of((update) => {
      if (update.docChanged) {
        onChangeRef.current?.(update.state.doc.toString())
      }
    })

    const state = EditorState.create({
      doc: value,
      extensions: [
        lineNumbers(),
        highlightActiveLineGutter(),
        highlightActiveLine(),
        foldGutter(),
        history(),
        indentOnInput(),
        bracketMatching(),
        indentUnit.of('    '),
        EditorState.tabSize.of(4),
        runKeymap,
        keymap.of([indentWithTab, ...defaultKeymap, ...historyKeymap]),
        langCompartment.current.of(languageExtension(language)),
        themeCompartment.current.of(isDark ? oneDark : lightTheme),
        readOnlyCompartment.current.of(EditorState.readOnly.of(readOnly)),
        updateListener,
        EditorView.lineWrapping,
        EditorView.theme({ '&': { height: '100%', fontSize: '13px' }, '.cm-scroller': { fontFamily: '"JetBrains Mono", monospace' } }),
      ],
    })

    const view = new EditorView({ state, parent: hostRef.current })
    viewRef.current = view
    return () => { view.destroy(); viewRef.current = null }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Push external value changes into the editor (e.g. switching files / reset).
  useEffect(() => {
    const view = viewRef.current
    if (!view) return
    const current = view.state.doc.toString()
    if (value !== current) {
      view.dispatch({ changes: { from: 0, to: current.length, insert: value } })
    }
  }, [value])

  // Reconfigure language without rebuilding the editor.
  useEffect(() => {
    viewRef.current?.dispatch({ effects: langCompartment.current.reconfigure(languageExtension(language)) })
  }, [language])

  // React to theme toggles live.
  useEffect(() => {
    viewRef.current?.dispatch({ effects: themeCompartment.current.reconfigure(isDark ? oneDark : lightTheme) })
  }, [isDark])

  // React to readOnly changes (e.g. lock the editor after solving).
  useEffect(() => {
    viewRef.current?.dispatch({ effects: readOnlyCompartment.current.reconfigure(EditorState.readOnly.of(readOnly)) })
  }, [readOnly])

  return <div ref={hostRef} className="h-full w-full overflow-hidden text-left" />
}
