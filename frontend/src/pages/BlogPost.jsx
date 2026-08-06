import { useParams, Link } from 'react-router-dom'
import { useState, useEffect } from 'react'
import { Clock, ArrowLeft, Tag, User, Calendar, ChevronRight } from 'lucide-react'
import DOMPurify from 'dompurify'
import api from '../api/client'
import { getCategoryClass } from '../data/blogFallback'
import MarketingPageShell from '../components/MarketingPageShell'
import { FixitPanel } from '../components/design'
import { usePageTitle } from '../hooks/usePageTitle'

// Audit Z3-12: the prose moved to the database (migration 0010) and to a
// dynamically-imported offline copy. Loaded once, only when the API cannot answer.
let fallbackCache = null
async function loadFallback(slug) {
  try {
    if (!fallbackCache) {
      fallbackCache = (await import('../data/blogArticles')).BLOG_ARTICLES
    }
    return slug ? fallbackCache[slug] || null : fallbackCache
  } catch {
    return null
  }
}

export default function BlogPost() {
  const { slug } = useParams()
  const [post, setPost] = useState(null)
  const [related, setRelated] = useState([])
  const [loading, setLoading] = useState(true)

  usePageTitle(
    post?.title,
    post?.excerpt || post?.subtitle,
    post ? { canonical: `${typeof window !== 'undefined' ? window.location.origin : ''}/blog/${slug}` } : undefined,
  )

  useEffect(() => {
    setLoading(true)
    let cancelled = false
    api.get(`/blog/${slug}/`, { silentError: true })
      .then(async res => {
        const apiPost = res.data
        // The database wins whenever it has a body. The previous version preferred
        // the bundled copy if the stored content was under 200 characters, so an
        // editor who shortened a post in the admin saw their edit silently ignored.
        // Only a genuinely empty body falls back now.
        let content = apiPost?.content || ''
        if (!content.trim()) {
          content = (await loadFallback(slug))?.content || ''
        }
        if (!cancelled) setPost({ ...apiPost, content, color: 'accent-cyan' })
      })
      .catch(async () => {
        // API unreachable — this is what the offline copy is for.
        const rich = await loadFallback(slug)
        if (!cancelled) setPost(rich || null)
      })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [slug])

  useEffect(() => {
    api.get('/blog/', { silentError: true })
      .then(res => {
        const list = (res.data || []).filter(p => p.slug !== slug).slice(0, 3)
        setRelated(list)
      })
      .catch(async () => {
        const all = await loadFallback(null)
        if (!all) return
        setRelated(
          Object.entries(all)
            .filter(([s]) => s !== slug)
            .slice(0, 3)
            .map(([s, p]) => ({ slug: s, title: p.title, category: p.category, readTime: p.readTime }))
        )
      })
  }, [slug])

  if (loading) {
    return (
      <MarketingPageShell narrow>
        <div className="flex items-center justify-center py-24">
          <div className="w-8 h-8 border-2 border-accent-cyan border-t-transparent rounded-full animate-spin" />
        </div>
      </MarketingPageShell>
    )
  }

  if (!post) {
    return (
      <MarketingPageShell narrow>
        <div className="py-12 text-center">
          <h1 className="text-3xl font-bold text-white mb-4">Post Not Found</h1>
          <p className="text-surface-400 mb-6">The blog post you&apos;re looking for doesn&apos;t exist.</p>
          <Link to="/blog" className="btn-primary px-6 py-2 inline-flex items-center gap-2">
            <ArrowLeft size={16} /> Back to Blog
          </Link>
        </div>
      </MarketingPageShell>
    )
  }

  // Simple markdown-like rendering
  const renderContent = (text) => {
    const lines = text.trim().split('\n')
    const elements = []
    let inCodeBlock = false
    let codeLines = []
    let codeLang = ''
    let inTable = false
    let tableRows = []

    const processInline = (text) => {
      // Bold
      text = text.replace(/\*\*(.+?)\*\*/g, '<strong class="text-white font-semibold">$1</strong>')
      // Italic
      text = text.replace(/\*(.+?)\*/g, '<em>$1</em>')
      // Inline code
      text = text.replace(/`([^`]+)`/g, '<code class="bg-surface-800 text-accent-cyan px-1.5 py-0.5 rounded text-sm font-mono">$1</code>')

      return DOMPurify.sanitize(text, {
        ALLOWED_TAGS: ['strong', 'em', 'code', 'br', 'span'],
        ALLOWED_ATTR: ['class'],
        ALLOW_DATA_ATTR: false,
        FORCE_BODY: true,
      })
    }

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i]

      // Code blocks
      if (line.startsWith('```')) {
        if (inCodeBlock) {
          elements.push(
            <div key={`code-${i}`} className="my-4">
              <pre className="bg-surface-900 border border-surface-700/50 rounded-lg p-4 overflow-x-auto">
                <code className="text-sm text-surface-300 font-mono whitespace-pre">
                  {codeLines.join('\n')}
                </code>
              </pre>
            </div>
          )
          codeLines = []
          inCodeBlock = false
        } else {
          codeLang = line.slice(3)
          inCodeBlock = true
        }
        continue
      }

      if (inCodeBlock) {
        codeLines.push(line)
        continue
      }

      // Table rows
      if (line.startsWith('|')) {
        if (!inTable) inTable = true
        // Skip separator rows
        if (line.match(/^\|[\s-|]+\|$/)) continue
        const cells = line.split('|').filter(c => c.trim()).map(c => c.trim())
        tableRows.push(cells)
        continue
      } else if (inTable) {
        // End table
        elements.push(
          <div key={`table-${i}`} className="my-4 overflow-x-auto">
            <table className="w-full text-sm border border-surface-700/50 rounded-lg overflow-hidden">
              <thead>
                <tr className="bg-surface-800/50">
                  {tableRows[0]?.map((cell, ci) => (
                    <th key={ci} className="px-3 py-2 text-left text-surface-300 font-medium border-b border-surface-700/50">{cell}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {tableRows.slice(1).map((row, ri) => (
                  <tr key={ri} className="border-b border-surface-800/50 hover:bg-surface-800/30">
                    {row.map((cell, ci) => (
                      <td key={ci} className="px-3 py-2 text-surface-400" dangerouslySetInnerHTML={{ __html: processInline(cell) }} />
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
        tableRows = []
        inTable = false
      }

      // Empty line
      if (line.trim() === '') continue

      // Headings
      if (line.startsWith('## ')) {
        elements.push(
          <h2 key={`h2-${i}`} className="text-xl font-bold text-white mt-8 mb-3">
            {line.slice(3)}
          </h2>
        )
        continue
      }
      if (line.startsWith('### ')) {
        elements.push(
          <h3 key={`h3-${i}`} className="text-lg font-semibold text-white mt-6 mb-2">
            {line.slice(4)}
          </h3>
        )
        continue
      }

      // List items
      if (line.startsWith('- ')) {
        elements.push(
          <li key={`li-${i}`} className="flex items-start gap-2 text-surface-300 ml-4 mb-1.5">
            <ChevronRight size={14} className="text-accent-cyan mt-0.5 shrink-0" />
            <span dangerouslySetInnerHTML={{ __html: processInline(line.slice(2)) }} />
          </li>
        )
        continue
      }
      // Numbered lists
      if (line.match(/^\d+\.\s/)) {
        const content = line.replace(/^\d+\.\s/, '')
        elements.push(
          <li key={`ol-${i}`} className="flex items-start gap-2 text-surface-300 ml-4 mb-1.5">
            <span className="text-accent-cyan font-bold text-sm mt-0.5 shrink-0">{line.match(/^(\d+)/)[1]}.</span>
            <span dangerouslySetInnerHTML={{ __html: processInline(content) }} />
          </li>
        )
        continue
      }

      // Regular paragraph
      elements.push(
        <p key={`p-${i}`} className="text-surface-300 leading-relaxed mb-3" dangerouslySetInnerHTML={{ __html: processInline(line) }} />
      )
    }

    // Flush remaining table
    if (inTable && tableRows.length > 0) {
      elements.push(
        <div key="table-end" className="my-4 overflow-x-auto">
          <table className="w-full text-sm border border-surface-700/50 rounded-lg overflow-hidden">
            <thead>
              <tr className="bg-surface-800/50">
                {tableRows[0]?.map((cell, ci) => (
                  <th key={ci} className="px-3 py-2 text-left text-surface-300 font-medium border-b border-surface-700/50">{cell}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {tableRows.slice(1).map((row, ri) => (
                <tr key={ri} className="border-b border-surface-800/50 hover:bg-surface-800/30">
                  {row.map((cell, ci) => (
                    <td key={ci} className="px-3 py-2 text-surface-400" dangerouslySetInnerHTML={{ __html: processInline(cell) }} />
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )
    }

    return elements
  }

  // Find related posts from API (fallback: static catalog)
  const relatedPosts = related

  return (
    <MarketingPageShell narrow>
      <article>
        <Link to="/blog" className="inline-flex items-center gap-2 text-sm text-surface-400 hover:text-white transition-colors mb-8">
          <ArrowLeft size={14} /> Back to Blog
        </Link>

        <header className="mb-8">
          <div className="flex flex-wrap items-center gap-3 mb-4">
            <span className={`text-xs font-semibold uppercase tracking-wider px-2 py-0.5 rounded border ${getCategoryClass(post.category)}`}>
              <Tag size={10} className="inline mr-1" />{post.category}
            </span>
            <span className="text-xs text-surface-500 flex items-center gap-1"><Clock size={10} />{post.readTime}</span>
          </div>
          <h1 className="text-3xl lg:text-4xl font-extrabold text-white mb-4 leading-tight">
            {post.title}
          </h1>
          <div className="flex items-center gap-4 text-sm text-surface-400">
            <span className="flex items-center gap-1.5"><User size={14} /> {post.author}</span>
            <span className="flex items-center gap-1.5"><Calendar size={14} /> {post.date}</span>
          </div>
        </header>

        <FixitPanel padding="p-6 md:p-8" className="mb-8">
          <div className="prose-dark">
            {renderContent(post.content)}
          </div>
        </FixitPanel>

        <FixitPanel hero padding="p-8" className="text-center relative overflow-hidden">
          <div className="absolute inset-0 bg-gradient-to-br from-accent-cyan/5 to-accent-purple/5" />
          <div className="relative">
            <h3 className="text-xl font-bold text-white mb-2">Ready to Practice?</h3>
            <p className="text-surface-400 text-sm mb-4">Stop reading, start doing. Real environments, real challenges.</p>
            <Link to="/register" className="btn-primary px-8 py-3 text-sm inline-block">Start Free &rarr;</Link>
          </div>
        </FixitPanel>

        {relatedPosts.length > 0 && (
          <div className="mt-12">
            <h3 className="text-lg font-semibold text-white mb-4">More Articles</h3>
            <div className="grid sm:grid-cols-3 gap-4">
              {relatedPosts.map(p => (
                <Link key={p.slug} to={`/blog/${p.slug}`} className="group">
                  <FixitPanel padding="p-4" className="h-full hover:border-accent-cyan/25 transition-colors">
                    <span className={`text-[10px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded border ${getCategoryClass(p.category)}`}>
                      {p.category}
                    </span>
                    <h4 className="text-sm font-medium text-white mt-2 group-hover:text-accent-cyan transition-colors leading-snug">
                      {p.title}
                    </h4>
                    <span className="text-xs text-surface-500 mt-2 block">{p.readTime}</span>
                  </FixitPanel>
                </Link>
              ))}
            </div>
          </div>
        )}
      </article>
    </MarketingPageShell>
  )
}
