import { Component } from 'react'
import { AlertTriangle, RefreshCw, Home } from 'lucide-react'
import { isChunkLoadError } from '../utils/lazyWithRetry'

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
              <pre className="text-xs text-surface-500 bg-surface-900 border border-surface-800 rounded-lg p-3 text-left overflow-auto max-h-32">
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
