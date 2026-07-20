import { Component } from 'react'
import { AlertTriangle, RefreshCw } from 'lucide-react'
import { isChunkLoadError } from '../utils/lazyWithRetry'

/**
 * Localized error boundary for heavy lab consoles (AWS, VMware, Interview, labs).
 * Prevents one console crash from taking down the entire app shell.
 */
export default class SimErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { error: null }
    this._autoResetDone = false
  }

  static getDerivedStateFromError(error) {
    return { error }
  }

  componentDidCatch(error, info) {
    console.error(`SimErrorBoundary [${this.props.name || 'lab'}]:`, error, info)
    // Missing-chunk failures cannot be recovered in place — auto-reload once.
    if (isChunkLoadError(error)) {
      this.hardReloadForChunk()
      return
    }
    // AWS/Terraform often crash from a corrupt persisted Zustand blob after a
    // deploy. Clear storage once and remount in place before asking the learner
    // to click anything. Guarded so a non-storage crash cannot loop forever.
    if (this.props.autoResetStorageOnError && !this._autoResetDone) {
      this._autoResetDone = true
      try { this.props.onResetStorage?.() } catch { /* ignore */ }
      try {
        if (this.props.resetStorageKey) localStorage.removeItem(this.props.resetStorageKey)
      } catch { /* ignore */ }
      setTimeout(() => {
        try { this.props.onReset?.() } catch { /* ignore */ }
        this.setState({ error: null })
      }, 0)
    }
  }

  get isChunkError() {
    return isChunkLoadError(this.state.error)
  }

  hardReloadForChunk = () => {
    const KEY = 'fixitlab-sim-chunk-reload'
    try {
      const last = Number(sessionStorage.getItem(KEY) || 0)
      if (Date.now() - last < 15000) return false
      sessionStorage.setItem(KEY, String(Date.now()))
    } catch { /* sessionStorage unavailable — fall through to reload anyway */ }
    try { window.location.reload() } catch { /* ignore */ }
    return true
  }

  handleReset = () => {
    if (this.isChunkError && this.hardReloadForChunk()) return
    try { this.props.onReset?.() } catch { /* ignore */ }
    this.setState({ error: null })
  }

  handleResetStorage = () => {
    if (this.props.resetStorageKey) {
      try { localStorage.removeItem(this.props.resetStorageKey) } catch { /* ignore */ }
    }
    try { this.props.onResetStorage?.() } catch { /* ignore */ }
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
            {(this.props.name === 'aws' || this.props.name === 'terraform') && (
              <p className="text-xs text-surface-500 max-w-md mt-2">
                AWS labs often fail after an update if an old console cache remains. Use <strong className="text-surface-300">Reset saved state</strong>, then reopen the lab.
              </p>
            )}
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
            <button
              type="button"
              onClick={() => {
                try {
                  sessionStorage.removeItem('fixitlab-sim-chunk-reload')
                  sessionStorage.removeItem('fixitlab-chunk-reload')
                  sessionStorage.removeItem('fixitlab:chunk-reload')
                } catch { /* */ }
                const u = new URL(window.location.href)
                u.searchParams.set('_r', String(Date.now()))
                window.location.replace(u.toString())
              }}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-surface-600 text-surface-300 text-sm hover:bg-surface-800"
            >
              Reload page
            </button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}
