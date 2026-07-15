import { useEffect, useRef } from 'react'
import { Terminal } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'
import { WebLinksAddon } from '@xterm/addon-web-links'
import '@xterm/xterm/css/xterm.css'
import { runAwsCommand, runTerraformCommand } from '../../utils/terraformAwsBridge'

/**
 * In-lab CloudShell for the Terraform workspace IDE.
 *
 * Unlike the generic AWS console CloudShell (which keeps its own isolated VFS),
 * this terminal runs `aws` and `terraform` commands against BOTH the shared AWS
 * store AND the learner's live IDE files (`filesRef`). That closes the cross-tech
 * loop: HCL written in the editor → `terraform apply` here → resources appear in
 * the AWS Console AND in `aws ec2 describe-instances` in this same terminal.
 *
 * `filesRef` is a ref so the terminal always reads the latest editor content
 * without needing to remount when the learner edits a .tf file.
 */
export default function TerraformAwsTerminal({ filesRef }) {
  const containerRef = useRef(null)
  const stateRef = useRef({ line: '', cursor: 0, history: [], histIdx: -1 })

  useEffect(() => {
    if (!containerRef.current) return undefined
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

    term.writeln('Welcome to AWS CloudShell (Terraform lab)')
    term.writeln('')
    term.writeln('Run \x1b[38;5;170mterraform\x1b[0m init / plan / apply / destroy against the files in the editor,')
    term.writeln('then verify with \x1b[38;5;214maws\x1b[0m ec2 describe-instances / aws s3 ls.')
    term.writeln('Resources you create appear in the AWS Console tab.')
    term.writeln('')

    const PROMPT = '\x1b[38;5;214m[cloudshell-user@ip-10-0-0-12 terraform]$\x1b[0m '
    const st = stateRef.current
    const prompt = () => term.write(`\r\n${PROMPT}`)
    prompt()

    const redraw = () => {
      term.write('\r\x1b[K')
      term.write(PROMPT + st.line)
    }

    const runLine = (raw) => {
      const line = raw.trim()
      if (!line) return
      st.history.push(line)
      let lines = []
      if (line === 'clear') { term.write('\x1b[2J\x1b[H'); return }
      if (line === 'aws' || line.startsWith('aws ')) {
        lines = runAwsCommand(line.split(/\s+/).slice(1))
      } else if (line === 'terraform' || line.startsWith('terraform ')) {
        lines = runTerraformCommand(line.split(/\s+/).slice(1), filesRef?.current || {})
      } else if (line === 'ls') {
        lines = Object.keys(filesRef?.current || {}).sort()
      } else if (line === 'help') {
        lines = ['Available: terraform <cmd>, aws <cmd>, ls, clear']
      } else {
        const cmd = line.split(/\s+/)[0]
        lines = [`${cmd}: command not found (this shell runs \`aws\`, \`terraform\`, \`ls\`, \`clear\`)`]
      }
      lines.forEach((l) => term.writeln(l))
    }

    const submit = () => {
      const line = st.line
      term.write('\r\n')
      st.line = ''
      st.cursor = 0
      st.histIdx = -1
      runLine(line)
      prompt()
    }

    const onData = (data) => {
      const code = data.charCodeAt(0)
      if (data === '\x03') { term.write('^C'); st.line = ''; st.cursor = 0; prompt(); return }
      if (data === '\r') { submit(); return }
      if (data === '\x7f') {
        if (st.cursor > 0) {
          st.line = st.line.slice(0, st.cursor - 1) + st.line.slice(st.cursor)
          st.cursor -= 1
          redraw()
          if (st.cursor < st.line.length) term.write(`\x1b[${st.line.length - st.cursor}D`)
        }
        return
      }
      if (data === '\x1b[A') {
        if (st.history.length) {
          if (st.histIdx === -1) st.histIdx = st.history.length
          st.histIdx = Math.max(0, st.histIdx - 1)
          st.line = st.history[st.histIdx] || ''
          st.cursor = st.line.length
          redraw()
        }
        return
      }
      if (data === '\x1b[B') {
        if (st.histIdx !== -1) {
          st.histIdx += 1
          if (st.histIdx >= st.history.length) { st.histIdx = -1; st.line = '' } else st.line = st.history[st.histIdx]
          st.cursor = st.line.length
          redraw()
        }
        return
      }
      if (data === '\x1b[D') { if (st.cursor > 0) { st.cursor -= 1; term.write('\x1b[D') } return }
      if (data === '\x1b[C') { if (st.cursor < st.line.length) { st.cursor += 1; term.write('\x1b[C') } return }
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
    // filesRef is a stable ref; the terminal reads .current at run time.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return <div ref={containerRef} style={{ width: '100%', height: '100%', background: '#16191f', padding: '4px 8px' }} />
}
