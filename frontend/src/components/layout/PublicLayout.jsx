import { Link, useLocation } from 'react-router-dom'
import { useThemeStore } from '../../store/themeStore'
import { useAuthStore } from '../../store/authStore'
import { Sun, Moon, Terminal, Menu, X, Bot } from 'lucide-react'
import { useState } from 'react'
import SupportBotWidget from '../SupportBotWidget'

const navLinkClass = (active) =>
  active
    ? 'text-sm text-white font-medium'
    : 'text-sm text-surface-400 hover:text-surface-100'

export default function PublicLayout({ children }) {
  const { theme, toggleTheme } = useThemeStore()
  const { isAuthenticated } = useAuthStore()
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const { pathname } = useLocation()
  const onBlog = pathname.startsWith('/blog')

  return (
    <div className="min-h-screen">
      {/* Navbar */}
      <nav className="fixed top-0 w-full z-50 border-b border-surface-700/50 bg-surface-950/90 backdrop-blur-xl">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2 text-lg font-bold">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center">
              <Terminal size={18} className="text-white" />
            </div>
            FixitLab
          </Link>
          <div className="flex items-center gap-4">
            <Link to="/about" className={`${navLinkClass(pathname === '/about')} hidden sm:block`}>About</Link>
            <Link to="/mock-interviews" className={`${navLinkClass(pathname === '/mock-interviews')} hidden sm:block`}>Interviews</Link>
            <Link to="/pricing" className={`${navLinkClass(pathname === '/pricing')} hidden sm:block`}>Pricing</Link>
            <Link to="/blog" className={`${navLinkClass(onBlog)} hidden sm:block`}>Blog</Link>
            <Link to="/faq" className={`${navLinkClass(pathname === '/faq')} hidden sm:block`}>FAQ</Link>
            <button
              type="button"
              onClick={() => window.dispatchEvent(new CustomEvent('fixitlab-support-open'))}
              className={`${navLinkClass(false)} hidden sm:inline-flex items-center gap-1`}
            >
              <Bot size={14} /> Help
            </button>
            <Link to="/verify-certificate" className={`${navLinkClass(pathname === '/verify-certificate')} hidden sm:block`}>Verify Certificate</Link>
            <button onClick={toggleTheme} className="p-2 rounded-lg hover:bg-surface-800 transition-colors">
              {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
            </button>
            {isAuthenticated ? (
              <Link to="/dashboard" className="btn-primary text-sm hidden sm:inline-flex">Dashboard</Link>
            ) : (
              <div className="hidden sm:flex items-center gap-2">
                <Link to="/login" className="btn-secondary text-sm">Log In</Link>
                <Link to="/register" className="btn-primary text-sm">Sign Up</Link>
              </div>
            )}
            {/* Mobile hamburger */}
            <button onClick={() => setMobileMenuOpen(!mobileMenuOpen)} className="sm:hidden p-2 text-surface-400" aria-label="Toggle menu">
              {mobileMenuOpen ? <X size={20} /> : <Menu size={20} />}
            </button>
          </div>
        </div>
        {/* Mobile dropdown menu */}
        {mobileMenuOpen && (
          <div className="sm:hidden border-t border-surface-700/50 bg-surface-950/95 backdrop-blur-xl">
            <div className="px-4 py-4 space-y-2">
              <Link to="/about" onClick={() => setMobileMenuOpen(false)} className="block text-sm text-surface-400 hover:text-white py-2">About</Link>
              <Link to="/mock-interviews" onClick={() => setMobileMenuOpen(false)} className="block text-sm text-surface-400 hover:text-white py-2">Interviews</Link>
              <Link to="/pricing" onClick={() => setMobileMenuOpen(false)} className="block text-sm text-surface-400 hover:text-white py-2">Pricing</Link>
              <Link to="/blog" onClick={() => setMobileMenuOpen(false)} className="block text-sm text-surface-400 hover:text-white py-2">Blog</Link>
              <Link to="/faq" onClick={() => setMobileMenuOpen(false)} className="block text-sm text-surface-400 hover:text-white py-2">FAQ</Link>
              <Link to="/verify-certificate" onClick={() => setMobileMenuOpen(false)} className="block text-sm text-surface-400 hover:text-white py-2">Verify Certificate</Link>
              <Link to="/contact" onClick={() => setMobileMenuOpen(false)} className="block text-sm text-surface-400 hover:text-white py-2">Contact</Link>
              <div className="pt-2 border-t border-surface-700/50 flex flex-col gap-2">
                {isAuthenticated ? (
                  <Link to="/dashboard" onClick={() => setMobileMenuOpen(false)} className="btn-primary text-sm text-center">Dashboard</Link>
                ) : (
                  <>
                    <Link to="/login" onClick={() => setMobileMenuOpen(false)} className="btn-secondary text-sm text-center">Log In</Link>
                    <Link to="/register" onClick={() => setMobileMenuOpen(false)} className="btn-primary text-sm text-center">Sign Up</Link>
                  </>
                )}
              </div>
            </div>
          </div>
        )}
      </nav>

      {/* Content */}
      <main className="pt-16">
        {children}
      </main>

      {/* Footer */}
      <footer className="border-t border-surface-700/50 bg-surface-900/30 py-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-8">
            <div>
              <h3 className="font-semibold mb-3">Product</h3>
              <div className="space-y-2 text-sm text-surface-400">
                <Link to="/pricing" className="block hover:text-surface-100">Pricing</Link>
                <Link to="/mock-interviews" className="block hover:text-surface-100">Mock Interviews</Link>
                <Link to="/scenarios" className="block hover:text-surface-100">Scenarios</Link>
                <Link to="/technologies" className="block hover:text-surface-100">Technologies</Link>
              </div>
            </div>
            <div>
              <h3 className="font-semibold mb-3">Resources</h3>
              <div className="space-y-2 text-sm text-surface-400">
                <Link to="/blog" className="block hover:text-surface-100">Blog</Link>
                <Link to="/faq" className="block hover:text-surface-100">FAQ</Link>
                <Link to="/about" className="block hover:text-surface-100">About</Link>
                <Link to="/verify-certificate" className="block hover:text-surface-100">Verify Certificate</Link>
              </div>
            </div>
            <div>
              <h3 className="font-semibold mb-3">Legal</h3>
              <div className="space-y-2 text-sm text-surface-400">
                <Link to="/privacy" className="block hover:text-surface-100">Privacy Policy</Link>
                <Link to="/terms" className="block hover:text-surface-100">Terms of Service</Link>
                <Link to="/contact" className="block hover:text-surface-100">Contact Us</Link>
              </div>
            </div>
            <div>
              <h3 className="font-semibold mb-3">Connect</h3>
              <div className="space-y-2 text-sm text-surface-400">
                <a href="https://github.com/fixitlab" className="block hover:text-surface-100" target="_blank" rel="noopener noreferrer">GitHub</a>
                <a href="https://twitter.com/fixitlab" className="block hover:text-surface-100" target="_blank" rel="noopener noreferrer">Twitter</a>
              </div>
            </div>
          </div>
          <div className="mt-8 pt-8 border-t border-surface-700/50 text-center text-sm text-surface-400">
            &copy; {new Date().getFullYear()} FixitLab. All rights reserved.
          </div>
        </div>
      </footer>
      <SupportBotWidget />
    </div>
  )
}
