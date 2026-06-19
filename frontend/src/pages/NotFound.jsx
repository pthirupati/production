import { Link } from 'react-router-dom'
import { Search, Home, ArrowLeft } from 'lucide-react'
import { FixitLogo } from '../components/design'

export default function NotFound() {
  return (
    <div className="min-h-screen bg-surface-950 flex items-center justify-center p-6 relative overflow-hidden">
      <div className="absolute inset-0 hero-grid opacity-30 pointer-events-none" />
      <div className="glow-orb-cyan absolute top-1/4 left-1/4 pointer-events-none" />
      <div className="glow-orb-purple absolute bottom-1/4 right-1/4 pointer-events-none" />

      <div className="max-w-md w-full text-center relative animate-fx-rise">
        <FixitLogo size="lg" className="inline-flex mb-8" />

        <div className="fx-panel p-10 space-y-6">
          <div className="relative">
            <h1 className="text-[100px] font-display font-black text-white/5 leading-none select-none">404</h1>
            <div className="absolute inset-0 flex items-center justify-center">
              <Search size={44} className="text-accent-cyan opacity-60" />
            </div>
          </div>
          <div>
            <p className="fx-page-eyebrow mb-2">Not found</p>
            <h2 className="text-2xl font-display font-bold text-white mb-2">Page not found</h2>
            <p className="text-surface-400 text-sm">
              The page you&apos;re looking for doesn&apos;t exist or has been moved.
            </p>
          </div>
          <div className="flex gap-3 justify-center pt-2">
            <Link
              to="/"
              className="flex items-center gap-2 px-4 py-2.5 btn-primary text-sm font-semibold"
            >
              <Home size={16} /> Home
            </Link>
            <button
              type="button"
              onClick={() => window.history.back()}
              className="flex items-center gap-2 px-4 py-2.5 btn-secondary text-sm font-medium"
            >
              <ArrowLeft size={16} /> Go Back
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
