import { Component } from 'react'
import { AlertTriangle, RefreshCw, Home } from '../ui/eagerIcons'
import { isChunkLoadError } from '../utils/lazyWithRetry'
import { reportClientError } from '../utils/reportClientError'

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  componentDidCatch(error, errorInfo) {
    console.error('ErrorBoundary caught:', error, errorInfo)
    // Audit Z6-6: previously this console.error was the only record, so a white
    // screen in production was invisible until someone wrote in. A chunk-load error
    // is a stale deploy, not a code bug, so it is reported under its own kind rather
    // than mixed in with real crashes.
    reportClientError(error, {
      componentStack: errorInfo?.componentStack,
      kind: isChunkLoadError(error) ? 'chunk_load' : 'react_error_boundary',
    })
    if (isChunkLoadError(error)) {
      const key = 'fixitlab-chunk-reload'
      if (!sessionStorage.getItem(key)) {
        sessionStorage.setItem(key, '1')
        window.location.reload()
      }
    }
  }

  handleRetry = () => {
    if (isChunkLoadError(this.state.error)) {
      window.location.reload()
      return
    }
    this.setState({ hasError: false, error: null })
  }

  handleGoHome = () => {
    window.location.href = '/'
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-surface-950 flex items-center justify-center p-6">
          <div className="max-w-md w-full text-center space-y-6">
            <div className="w-16 h-16 mx-auto rounded-2xl bg-accent-red/10 flex items-center justify-center">
              <AlertTriangle size={32} className="text-accent-red" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-white mb-2">Something went wrong</h1>
              <p className="text-surface-400 text-sm">
                An unexpected error occurred. Please try again or return to the home page.
              </p>
            </div>
            {this.state.error && (
              /* surface-400, not surface-500: this is the only copy telling the user
                 WHAT broke, so it has to clear AA. On surface-900 the 500 token
                 measures 3.50:1 in light mode (--s-500 120,135,155 on --s-900
                 248,250,252); 400 measures 6.16:1. Fixed here rather than by
                 redefining --s-500, which is shared with borders/disabled states. */
              <pre className="text-xs text-surface-400 bg-surface-900 border border-surface-800 rounded-lg p-3 text-left overflow-auto max-h-32">
                {this.state.error.message}
              </pre>
            )}
            <div className="flex gap-3 justify-center">
              <button
                onClick={this.handleRetry}
                className="flex items-center gap-2 px-4 py-2 bg-accent-cyan/10 text-accent-cyan border border-accent-cyan/20 rounded-lg hover:bg-accent-cyan/20 transition-colors text-sm font-medium"
              >
                <RefreshCw size={16} /> Try Again
              </button>
              <button
                onClick={this.handleGoHome}
                className="flex items-center gap-2 px-4 py-2 bg-surface-800 text-surface-300 border border-surface-700 rounded-lg hover:bg-surface-700 transition-colors text-sm font-medium"
              >
                <Home size={16} /> Home
              </button>
            </div>
          </div>
        </div>
      )
    }

    return this.props.children
  }
}
