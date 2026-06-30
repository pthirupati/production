import { useEffect, useRef } from 'react'
import { Terminal } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'
import { WebLinksAddon } from '@xterm/addon-web-links'
import '@xterm/xterm/css/xterm.css'
import { Shell } from './shell'
import { defaultUser } from './vfs'
import { useAwsStore } from '../store/awsStore'

// Full xterm.js terminal bound to a simulated EC2 instance. Handles line
// editing, history (up/down), Ctrl+C interrupt, and runs the Shell interpreter.
export default function AwsTerminal({ instance, username, cloudShell = false }) {
  const containerRef = useRef(null)
  const termRef = useRef(null)
  const shellRef = useRef(null)
  const stateRef = useRef({ line: '', cursor: 0, histIdx: -1, running: false })

  useEffect(() => {
    if (!containerRef.current) return undefined
    const store = useAwsStore.getState()
    const inst = instance ? { ...instance } : {
      id: 'cloudshell', region: store.region, os: 'amazon-linux-2023',
      type: 't3.micro', privateIp: '10.0.0.12', publicIp: '', rootVolume: null, iamRole: 'CloudShellRole',
    }
    if (username) inst.sshUser = username
    const term = new Terminal({
      fontFamily: '"SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace',
      fontSize: 13,
      theme: { background: '#16191f', foreground: '#e7ebef', cursor: '#ff9900', selectionBackground: '#37475a' },
      cursorBlink: true,
      convertEol: true,
    })
    const fit = new FitAddon()
    term.loadAddon(fit)
    term.loadAddon(new WebLinksAddon())
    term.open(containerRef.current)
    try { fit.fit() } catch { /* container not measured yet */ }
    termRef.current = term

    const shell = new Shell({ instance: inst, store, cloudShell })
    shellRef.current = shell
    const write = (t) => term.write(t)

    // Welcome banner
    if (cloudShell) {
      term.writeln('Welcome to AWS CloudShell!')
      term.writeln('')
      term.writeln('Type "aws help" for AWS CLI or "terraform -help" for IaC against this simulation.')
      term.writeln('Starter template: ~/main.tf')
      term.writeln('')
    } else {
      const user = username || defaultUser(inst.os)
      term.writeln('\x1b[33mEC2 Instance Connect\x1b[0m')
      term.writeln(`Connecting to ${inst.id} (${inst.os}) as ${user}...`)
      const moded = (shell.fs['/etc/motd']?.content || '').split('\n')
      moded.forEach((l) => term.writeln(l))
      term.writeln(`Last login: ${new Date().toUTCString()} from 203.0.113.10`)
    }
    const prompt = () => term.write(`\r\n${shell.prompt()}`)
    prompt()

    const st = stateRef.current
    const redraw = () => {
      // Clear current line and rewrite prompt + buffer
      term.write('\r\x1b[K')
      term.write(shell.prompt() + st.line)
    }

    const submit = async () => {
      const line = st.line
      term.write('\r\n')
      st.line = ''
      st.cursor = 0
      st.histIdx = -1
      if (!line.trim()) { prompt(); return }
      st.running = true
      shell.onExit = () => { term.writeln('\r\nConnection to instance closed.'); }
      shell._aborted = false
      try {
        await shell.run(line, write)
      } catch (e) {
        term.writeln(`\r\n\x1b[31m${e?.message || e}\x1b[0m`)
      }
      st.running = false
      prompt()
    }

    const onData = (data) => {
      const code = data.charCodeAt(0)
      // Ctrl+C
      if (data === '\x03') {
        if (st.running) {
          shell._aborted = true
          if (shell._interrupt) shell._interrupt()
          else { term.write('^C'); }
          return
        }
        term.write('^C')
        st.line = ''
        st.cursor = 0
        prompt()
        return
      }
      if (st.running) return // ignore input while a command streams (except Ctrl+C above)
      // Enter
      if (data === '\r') { submit(); return }
      // Backspace
      if (data === '\x7f') {
        if (st.cursor > 0) { st.line = st.line.slice(0, st.cursor - 1) + st.line.slice(st.cursor); st.cursor -= 1; redraw(); if (st.cursor < st.line.length) term.write(`\x1b[${st.line.length - st.cursor}D`) }
        return
      }
      // Arrow keys (history + cursor)
      if (data === '\x1b[A') { // up
        if (shell.history.length) { if (st.histIdx === -1) st.histIdx = shell.history.length; st.histIdx = Math.max(0, st.histIdx - 1); st.line = shell.history[st.histIdx] || ''; st.cursor = st.line.length; redraw() }
        return
      }
      if (data === '\x1b[B') { // down
        if (st.histIdx !== -1) { st.histIdx += 1; if (st.histIdx >= shell.history.length) { st.histIdx = -1; st.line = '' } else st.line = shell.history[st.histIdx]; st.cursor = st.line.length; redraw() }
        return
      }
      if (data === '\x1b[D') { if (st.cursor > 0) { st.cursor -= 1; term.write('\x1b[D') } return }
      if (data === '\x1b[C') { if (st.cursor < st.line.length) { st.cursor += 1; term.write('\x1b[C') } return }
      // Printable
      if (code >= 32 && code !== 127) {
        st.line = st.line.slice(0, st.cursor) + data + st.line.slice(st.cursor)
        st.cursor += data.length
        if (st.cursor === st.line.length) term.write(data)
        else { redraw(); term.write(`\x1b[${st.line.length - st.cursor}D`) }
      }
    }
    const disp = term.onData(onData)

    const ro = new ResizeObserver(() => { try { fit.fit() } catch { /* noop */ } })
    ro.observe(containerRef.current)

    return () => { disp.dispose(); ro.disconnect(); term.dispose() }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [instance?.id, username, cloudShell])

  return <div ref={containerRef} style={{ width: '100%', height: '100%', background: '#16191f', padding: '4px 8px' }} />
}
