import { Component } from 'react'
import { AlertTriangle, RefreshCw } from 'lucide-react'
import { isChunkLoadError } from '../utils/lazyWithRetry'

/**
 * Localized error boundary for heavy simulators (AWS, VMware, Interview, labs).
 * Prevents one simulator crash from taking down the entire app shell.
 */
export default class SimErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { error: null }
  }

  static getDerivedStateFromError(error) {
    return { error }
  }

  componentDidCatch(error, info) {
    console.error(`SimErrorBoundary [${this.props.name || 'sim'}]:`, error, info)
    // A missing-chunk failure cannot be recovered in place, so auto-reload once
    // (loop-guarded) the moment we catch it — the learner never has to click
    // "Try again" on an error that a click could never fix.
    if (isChunkLoadError(error)) this.hardReloadForChunk()
  }

  // A ChunkLoadError means the lazy sim chunk itself could not be fetched
  // (stale deploy: the cached index.html references hashed chunks that no longer
  // exist). This is the documented cause of "Something went wrong loading this
  // simulator" — and neither re-rendering the SAME failed lazy component ("Try
  // again") nor clearing the persisted store ("Reset saved state") can fix it:
  // the module is simply missing. The ONLY recovery is a hard reload so the
  // browser revalidates index.html and fetches the current chunk. Detect this
  // and reload once (loop-guarded) instead of leaving the learner stuck.
  get isChunkError() {
    return isChunkLoadError(this.state.error)
  }

  hardReloadForChunk = () => {
    const KEY = 'fixitlab-sim-chunk-reload'
    try {
      const last = Number(sessionStorage.getItem(KEY) || 0)
      // Loop guard: only auto-reload once per 15s so a genuinely broken deploy
      // can't trap the tab in a reload cycle.
      if (Date.now() - last < 15000) return false
      sessionStorage.setItem(KEY, String(Date.now()))
    } catch { /* sessionStorage unavailable — fall through to reload anyway */ }
    try { window.location.reload() } catch { /* ignore */ }
    return true
  }

  handleReset = () => {
    // For a missing-chunk error, re-rendering the same lazy component just
    // re-throws — force a hard reload to fetch the current assets instead.
    if (this.isChunkError && this.hardReloadForChunk()) return
    try { this.props.onReset?.() } catch { /* ignore */ }
    this.setState({ error: null })
  }

  handleResetStorage = () => {
    // 1) Clear the persisted blob so a corrupt/old payload can't rehydrate again.
    if (this.props.resetStorageKey) {
      try { localStorage.removeItem(this.props.resetStorageKey) } catch { /* ignore */ }
    }
    // 2) Re-seed the live in-memory store. Without this, "Try again" would
    //    re-render the same broken in-memory state and crash immediately —
    //    clearing localStorage alone only helps after a full reload.
    try { this.props.onResetStorage?.() } catch { /* ignore */ }
    // 3) Recover in place (no full reload needed).
    this.handleReset()
  }

  render() {
    if (this.state.error) {
      return (
        <div className="flex flex-1 min-h-[240px] flex-col items-center justify-center gap-4 bg-surface-950 p-6 text-center">
          <AlertTriangle className="text-amber-400" size={36} aria-hidden />
          <div>
            <h2 className="text-base font-semibold text-white mb-1">
              {this.props.title || 'Lab console error'}
            </h2>
            <p className="text-sm text-surface-400 max-w-md">
              {this.props.message || 'Something went wrong loading this lab console. Try resetting or reload the page.'}
            </p>
          </div>
          <div className="flex flex-wrap gap-2 justify-center">
            <button
              type="button"
              onClick={this.handleReset}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-accent-cyan/40 text-accent-cyan text-sm hover:bg-accent-cyan/10"
            >
              <RefreshCw size={14} /> Try again
            </button>
            {(this.props.resetStorageKey || this.props.onResetStorage) && (
              <button
                type="button"
                onClick={this.handleResetStorage}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-surface-600 text-surface-300 text-sm hover:bg-surface-800"
              >
                Reset saved state
              </button>
            )}
          </div>
        </div>
      )
    }
    return this.props.children
  }
}
