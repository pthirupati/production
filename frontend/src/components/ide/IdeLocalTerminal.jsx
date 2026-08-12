/**
 * Local xterm for coding-mode labs (audit Y2e integrated terminal half).
 *
 * Not a real shell / WebSocket — echoes typed lines and accepts writeln() from
 * Run/Check so the Terminal tab is interactive rather than a read-only <pre>.
 */
import { useEffect, useRef, useImperativeHandle, forwardRef } from 'react'
import { Terminal } from '@xterm/xterm'
import '@xterm/xterm/css/xterm.css'

const IdeLocalTerminal = forwardRef(function IdeLocalTerminal(
  { initialText = '', className = '' },
  ref,
) {
  const hostRef = useRef(null)
  const termRef = useRef(null)
  const lineRef = useRef('')

  useImperativeHandle(ref, () => ({
    writeln(line) {
      const t = termRef.current
      if (!t) return
      const text = String(line ?? '')
      t.writeln(text)
    },
    clear() {
      termRef.current?.clear()
      termRef.current?.write('$ ')
    },
  }), [])

  useEffect(() => {
    if (!hostRef.current || termRef.current) return undefined
    const term = new Terminal({
      convertEol: true,
      fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
      fontSize: 12,
      theme: {
        background: '#0d1117',
        foreground: '#e6edf3',
        cursor: '#58a6ff',
      },
      cursorBlink: true,
      disableStdin: false,
    })
    term.open(hostRef.current)
    termRef.current = term
    term.writeln('FixitLab IDE terminal (local) — type help, clear, or echo …')
    if (initialText) {
      initialText.split('\n').forEach((ln) => { if (ln) term.writeln(ln) })
    }
    term.write('$ ')

    const onData = (data) => {
      if (data === '\r') {
        const cmd = lineRef.current.trim()
        term.write('\r\n')
        if (cmd === 'help') {
          term.writeln('Builtins: help, clear, echo <text> — Run/Check also append here.')
        } else if (cmd === 'clear') {
          term.clear()
        } else if (cmd.startsWith('echo ')) {
          term.writeln(cmd.slice(5))
        } else if (cmd) {
          term.writeln(`lab: command not found: ${cmd.split(/\s+/)[0]}`)
        }
        lineRef.current = ''
        term.write('$ ')
        return
      }
      if (data === '\u007f') {
        if (lineRef.current.length) {
          lineRef.current = lineRef.current.slice(0, -1)
          term.write('\b \b')
        }
        return
      }
      if (data >= ' ' || data === '\t') {
        lineRef.current += data
        term.write(data)
      }
    }
    term.onData(onData)
    return () => {
      term.dispose()
      termRef.current = null
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps -- mount once
  }, [])

  return (
    <div
      ref={hostRef}
      className={className}
      style={{ width: '100%', minHeight: 160, height: '100%' }}
      data-testid="ide-local-terminal"
    />
  )
})

export default IdeLocalTerminal
