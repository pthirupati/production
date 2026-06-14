import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { Terminal, Clock, ArrowRight, Tag, User, ChevronRight } from 'lucide-react'
import api from '../api/client'

const fallbackPosts = [
  {
    slug: 'teams-coupons-and-security',
    title: 'Teams, Coupons, and Platform Security — What\'s New',
    excerpt: 'Enterprise seat licensing, checkout coupon codes, admin security dashboards, and community threads with screenshot attachments.',
    category: 'Product',
    author: 'Platform Team',
    date: 'June 5, 2026',
    readTime: '4 min read',
    color: 'accent-green',
    featured: true,
  },
]

const colorMap = {
  Product: 'accent-green',
  Education: 'accent-cyan',
  Linux: 'accent-green',
  Architecture: 'accent-purple',
  Networking: 'accent-green',
  Engineering: 'accent-cyan',
}

export default function Blog() {
  const [posts, setPosts] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.get('/blog/')
      .then(res => {
        const data = (res.data || []).map(p => ({
          ...p,
          color: colorMap[p.category] || 'accent-cyan',
        }))
        setPosts(data.length ? data : fallbackPosts)
      })
      .catch(() => setPosts(fallbackPosts))
      .finally(() => setLoading(false))
  }, [])

  const featured = posts.find(p => p.featured) || posts[0]
  const rest = posts.filter(p => p.slug !== featured?.slug)

  if (loading) {
    return (
      <div className="flex justify-center py-20">
        <div className="w-8 h-8 border-2 border-accent-cyan border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  return (
    <div className="max-w-5xl mx-auto px-4 py-12 space-y-10">
      <div className="text-center space-y-3">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-accent-cyan/10 text-accent-cyan text-xs font-medium">
          <Terminal size={14} /> FixitLab Blog
        </div>
        <h1 className="text-3xl md:text-4xl font-bold text-white">Engineering insights & product updates</h1>
        <p className="text-surface-400 max-w-xl mx-auto">Hands-on SRE tips, architecture deep dives, and platform news.</p>
      </div>

      {featured && (
        <Link to={`/blog/${featured.slug}`} className="block glass-card overflow-hidden group hover:ring-2 hover:ring-accent-cyan/30 transition-all">
          <div className="p-8 md:p-10">
            <span className={`text-xs font-semibold uppercase tracking-wider text-${featured.color}`}>{featured.category}</span>
            <h2 className="text-2xl md:text-3xl font-bold text-white mt-2 group-hover:text-accent-cyan transition-colors">{featured.title}</h2>
            <p className="text-surface-400 mt-3 max-w-2xl">{featured.excerpt}</p>
            <div className="flex items-center gap-4 mt-6 text-sm text-surface-500">
              <span className="flex items-center gap-1"><User size={14} /> {featured.author}</span>
              <span className="flex items-center gap-1"><Clock size={14} /> {featured.readTime}</span>
            </div>
            <span className="inline-flex items-center gap-1 mt-4 text-accent-cyan text-sm font-medium">
              Read article <ArrowRight size={14} />
            </span>
          </div>
        </Link>
      )}

      <div className="grid md:grid-cols-2 gap-6">
        {rest.map(post => (
          <Link key={post.slug} to={`/blog/${post.slug}`} className="glass-card p-6 group hover:ring-1 hover:ring-surface-700 transition-all">
            <span className="text-xs text-surface-500 flex items-center gap-1"><Tag size={12} /> {post.category}</span>
            <h3 className="text-lg font-semibold text-white mt-2 group-hover:text-accent-cyan transition-colors">{post.title}</h3>
            <p className="text-sm text-surface-400 mt-2 line-clamp-2">{post.excerpt}</p>
            <div className="flex items-center justify-between mt-4 text-xs text-surface-500">
              <span>{post.date}</span>
              <ChevronRight size={14} className="text-surface-600 group-hover:text-accent-cyan" />
            </div>
          </Link>
        ))}
      </div>
    </div>
  )
}
