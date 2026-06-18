import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import api from '../api/client'
import { ArrowLeft, Sparkles } from 'lucide-react'

function markdownToHtml(md) {
  if (!md) return ''
  return md
    // Headings
    .replace(/^### (.+)$/gm, '<h3 class="text-lg font-bold text-white mt-6 mb-2">$1</h3>')
    .replace(/^## (.+)$/gm, '<h2 class="text-xl font-bold text-accent-cyan mt-8 mb-3">$1</h2>')
    .replace(/^# (.+)$/gm, '<h1 class="text-2xl font-black text-white mt-8 mb-4">$1</h1>')
    // Bold
    .replace(/\*\*(.+?)\*\*/g, '<strong class="text-white font-semibold">$1</strong>')
    // Italic
    .replace(/\*(.+?)\*/g, '<em class="text-surface-300 italic">$1</em>')
    // Inline code
    .replace(/`([^`]+)`/g, '<code class="px-1.5 py-0.5 bg-surface-800 rounded text-accent-green font-mono text-sm">$1</code>')
    // Unordered list items
    .replace(/^- (.+)$/gm, '<li class="flex items-start gap-2 text-surface-300"><span class="text-accent-cyan mt-1.5 shrink-0">&#x2022;</span><span>$1</span></li>')
    // Wrap consecutive li elements
    .replace(/(<li[^>]*>.*?<\/li>\n?)+/gs, '<ul class="space-y-1.5 my-3">$&</ul>')
    // Horizontal rules
    .replace(/^---$/gm, '<hr class="border-surface-700/50 my-6" />')
    // Paragraphs: lines that aren't html tags
    .replace(/^(?!<[a-z])(.+)$/gm, '<p class="text-surface-300 leading-relaxed">$1</p>')
    // Collapse multiple blank lines
    .replace(/\n{3,}/g, '\n\n')
}

export default function Changelog() {
  const [changelog, setChangelog] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)

  useEffect(() => {
    api.get('/config/', { silentError: true })
      .then(res => {
        setChangelog(res.data?.platform_config?.changelog || res.data?.changelog || null)
      })
      .catch(() => setError(true))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="min-h-screen bg-surface-950 text-white">
      {/* Background effects */}
      <div className="fixed inset-0 bg-grid-pattern opacity-[0.04] pointer-events-none" />
      <div className="fixed top-0 left-1/4 w-96 h-96 bg-accent-cyan/5 rounded-full blur-3xl pointer-events-none" />
      <div className="fixed bottom-1/4 right-1/4 w-72 h-72 bg-accent-purple/5 rounded-full blur-3xl pointer-events-none" />

      <div className="relative max-w-3xl mx-auto px-4 py-12">
        {/* Back link */}
        <Link
          to="/"
          className="inline-flex items-center gap-2 text-sm text-surface-400 hover:text-accent-cyan transition-colors mb-8 group"
        >
          <ArrowLeft size={16} className="group-hover:-translate-x-0.5 transition-transform" />
          Back to Home
        </Link>

        {/* Header */}
        <div className="mb-10">
          <div className="flex items-center gap-2 mb-3">
            <div className="w-2 h-2 rounded-full bg-accent-cyan animate-pulse" />
            <span className="text-xs font-semibold text-accent-cyan/80 uppercase tracking-widest">What's New</span>
          </div>
          <h1 className="text-4xl font-black tracking-tight mb-3">
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-accent-cyan via-accent-blue to-accent-purple">
              Platform Updates
            </span>
          </h1>
          <p className="text-surface-400 text-base">Stay up to date with the latest improvements, features, and fixes.</p>
        </div>

        {/* Content card */}
        <div className="glass-card p-8 relative overflow-hidden">
          <div className="absolute inset-0 bg-gradient-to-br from-accent-cyan/[0.03] via-transparent to-accent-purple/[0.03] pointer-events-none" />

          {loading && (
            <div className="flex items-center justify-center py-16">
              <div className="flex flex-col items-center gap-3">
                <div className="w-8 h-8 border-2 border-accent-cyan/30 border-t-accent-cyan rounded-full animate-spin" />
                <span className="text-sm text-surface-500">Loading updates...</span>
              </div>
            </div>
          )}

          {!loading && error && (
            <div className="text-center py-16">
              <Sparkles size={32} className="text-surface-600 mx-auto mb-3" />
              <p className="text-surface-400">Could not load the changelog. Please try again later.</p>
            </div>
          )}

          {!loading && !error && !changelog && (
            <div className="text-center py-16">
              <Sparkles size={32} className="text-surface-600 mx-auto mb-3" />
              <p className="text-surface-400">No updates published yet. Check back soon!</p>
            </div>
          )}

          {!loading && !error && changelog && (
            <div
              className="prose-custom relative"
              dangerouslySetInnerHTML={{ __html: markdownToHtml(changelog) }}
            />
          )}
        </div>

        {/* Footer link */}
        <div className="mt-8 text-center">
          <Link
            to="/"
            className="inline-flex items-center gap-2 text-sm text-surface-400 hover:text-accent-cyan transition-colors"
          >
            <ArrowLeft size={14} />
            Back to Home
          </Link>
        </div>
      </div>
    </div>
  )
}
