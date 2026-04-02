import { Link } from 'react-router-dom'
import { Search, Home, ArrowLeft } from 'lucide-react'

export default function NotFound() {
  return (
    <div className="min-h-screen bg-surface-950 flex items-center justify-center p-6">
      <div className="max-w-md w-full text-center space-y-6">
        <div className="relative">
          <h1 className="text-[120px] font-black text-surface-800 leading-none select-none">404</h1>
          <div className="absolute inset-0 flex items-center justify-center">
            <Search size={48} className="text-accent-cyan opacity-50" />
          </div>
        </div>
        <div>
          <h2 className="text-2xl font-bold text-white mb-2">Page not found</h2>
          <p className="text-surface-400 text-sm">
            The page you're looking for doesn't exist or has been moved.
          </p>
        </div>
        <div className="flex gap-3 justify-center">
          <Link
            to="/"
            className="flex items-center gap-2 px-4 py-2 bg-accent-cyan text-surface-950 rounded-lg hover:bg-accent-cyan/90 transition-colors text-sm font-semibold"
          >
            <Home size={16} /> Home
          </Link>
          <button
            onClick={() => window.history.back()}
            className="flex items-center gap-2 px-4 py-2 bg-surface-800 text-surface-300 border border-surface-700 rounded-lg hover:bg-surface-700 transition-colors text-sm font-medium"
          >
            <ArrowLeft size={16} /> Go Back
          </button>
        </div>
      </div>
    </div>
  )
}
