import { useState, useEffect, useMemo } from 'react'
import { Link } from 'react-router-dom'
import {
  Terminal, Clock, ArrowRight, Tag, User, ChevronRight, BookOpen, Sparkles, TrendingUp,
  Rss, Search,
} from 'lucide-react'
import api from '../api/client'
import { BLOG_FALLBACK_POSTS, BLOG_CATEGORIES, getCategoryClass } from '../data/blogFallback'

function mergePosts(apiPosts) {
  const bySlug = new Map()
  for (const p of BLOG_FALLBACK_POSTS) bySlug.set(p.slug, { ...p })
  for (const p of apiPosts || []) bySlug.set(p.slug, { ...bySlug.get(p.slug), ...p })
  return Array.from(bySlug.values()).sort((a, b) => {
    if (a.featured && !b.featured) return -1
    if (!a.featured && b.featured) return 1
    return 0
  })
}

const CATEGORY_GRADIENTS = {
  'SRE': 'from-cyan-500/25 to-blue-600/15',
  'Kubernetes': 'from-blue-500/25 to-indigo-600/15',
  'Linux': 'from-orange-500/25 to-red-600/15',
  'DevOps': 'from-green-500/25 to-emerald-600/15',
  'Cloud': 'from-purple-500/25 to-violet-600/15',
  'Security': 'from-red-500/25 to-pink-600/15',
  'Networking': 'from-teal-500/25 to-cyan-600/15',
  'Platform': 'from-amber-500/25 to-yellow-600/15',
  'default': 'from-accent-cyan/20 to-accent-purple/15',
}

function CategoryCover({ category, featured = false }) {
  const grad = CATEGORY_GRADIENTS[category] || CATEGORY_GRADIENTS.default
  return (
    <div className={`w-full ${featured ? 'h-40 md:h-full md:min-h-[200px]' : 'h-28'} rounded-xl bg-gradient-to-br ${grad} border border-white/5 flex items-center justify-center relative overflow-hidden shrink-0`}>
      <div className="absolute inset-0 opacity-10" style={{
        backgroundImage: 'repeating-linear-gradient(0deg, transparent, transparent 28px, rgba(255,255,255,0.05) 28px, rgba(255,255,255,0.05) 29px), repeating-linear-gradient(90deg, transparent, transparent 28px, rgba(255,255,255,0.05) 28px, rgba(255,255,255,0.05) 29px)',
      }} />
      <Terminal size={featured ? 36 : 28} className="text-white/30" />
    </div>
  )
}

function PostCardSkeleton() {
  return (
    <div className="glass-card overflow-hidden animate-pulse">
      <div className="h-28 bg-surface-800/60 rounded-t-xl" />
      <div className="p-5 space-y-3">
        <div className="h-3 w-16 bg-surface-700/60 rounded-full" />
        <div className="h-5 bg-surface-700/60 rounded" />
        <div className="h-4 w-3/4 bg-surface-700/40 rounded" />
        <div className="h-3 w-1/2 bg-surface-700/30 rounded" />
      </div>
    </div>
  )
}

export default function Blog() {
  const [posts, setPosts] = useState(BLOG_FALLBACK_POSTS)
  const [loading, setLoading] = useState(true)
  const [activeCategory, setActiveCategory] = useState('All')
  const [searchQuery, setSearchQuery] = useState('')

  useEffect(() => {
    api.get('/blog/')
      .then(res => setPosts(mergePosts(res.data)))
      .catch(() => setPosts(BLOG_FALLBACK_POSTS))
      .finally(() => setLoading(false))
  }, [])

  const categories = useMemo(() => {
    const fromPosts = [...new Set(posts.map(p => p.category).filter(Boolean))]
    return ['All', ...BLOG_CATEGORIES.filter(c => c !== 'All' && fromPosts.includes(c)),
      ...fromPosts.filter(c => !BLOG_CATEGORIES.includes(c))]
  }, [posts])

  const filtered = useMemo(() => {
    let base = activeCategory === 'All' ? posts : posts.filter(p => p.category === activeCategory)
    if (searchQuery.trim().length > 1) {
      const q = searchQuery.toLowerCase()
      base = base.filter(p =>
        p.title?.toLowerCase().includes(q) ||
        p.excerpt?.toLowerCase().includes(q) ||
        p.author?.toLowerCase().includes(q)
      )
    }
    return base
  }, [posts, activeCategory, searchQuery])

  const featured = filtered.find(p => p.featured) || filtered[0]
  const rest = filtered.filter(p => p.slug !== featured?.slug)

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 py-10 md:py-14 space-y-10">
      {/* Hero */}
      <div className="text-center space-y-4 animate-fade-in">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-accent-cyan/10 text-accent-cyan text-xs font-medium border border-accent-cyan/20">
          <Rss size={13} /> FixitLab Blog
        </div>
        <h1 className="text-3xl md:text-5xl font-bold tracking-tight">
          <span className="text-white">Engineering insights</span>
          <br />
          <span className="bg-gradient-to-r from-accent-cyan via-accent-blue to-accent-purple bg-clip-text text-transparent">
            &amp; product updates
          </span>
        </h1>
        <p className="text-surface-400 max-w-2xl mx-auto text-base md:text-lg leading-relaxed">
          Hands-on SRE playbooks, architecture deep dives, and platform news from the team building
          real troubleshooting labs for Linux, Kubernetes, cloud, and more.
        </p>
        <div className="flex flex-wrap items-center justify-center gap-6 pt-1 text-sm text-surface-500">
          <span className="inline-flex items-center gap-1.5"><BookOpen size={14} /> {posts.length} articles</span>
          <span className="inline-flex items-center gap-1.5"><Tag size={14} /> {categories.length - 1} topics</span>
          <span className="inline-flex items-center gap-1.5"><TrendingUp size={14} /> Updated regularly</span>
        </div>
      </div>

      {/* Search + Category filters */}
      <div className="space-y-4 animate-slide-up">
        <div className="relative max-w-md mx-auto">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-surface-500" />
          <input
            type="text"
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            placeholder="Search articles…"
            className="input-field w-full pl-10 py-2.5 text-sm"
          />
        </div>
        <div className="flex flex-wrap justify-center gap-2">
          {categories.map(cat => (
            <button
              key={cat}
              type="button"
              onClick={() => setActiveCategory(cat)}
              className={`px-4 py-1.5 rounded-full text-sm font-medium transition-all border ${
                activeCategory === cat
                  ? 'bg-accent-cyan/15 text-accent-cyan border-accent-cyan/40'
                  : 'bg-surface-900/50 text-surface-400 border-surface-700/50 hover:text-white hover:border-surface-600'
              }`}
            >
              {cat}
            </button>
          ))}
        </div>
      </div>

      {/* Loading skeletons */}
      {loading && (
        <div className="space-y-6">
          <div className="glass-card p-8 animate-pulse">
            <div className="h-48 bg-surface-800/60 rounded-xl mb-6" />
            <div className="space-y-3">
              <div className="h-4 w-24 bg-surface-700/60 rounded-full" />
              <div className="h-7 w-3/4 bg-surface-700/60 rounded" />
              <div className="h-4 bg-surface-700/40 rounded" />
            </div>
          </div>
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            {[1,2,3].map(i => <PostCardSkeleton key={i} />)}
          </div>
        </div>
      )}

      {!loading && filtered.length === 0 && (
        <div className="glass-card p-12 text-center animate-fade-in">
          <BookOpen size={40} className="text-surface-600 mx-auto mb-4" />
          <p className="text-surface-400 text-lg mb-2">No articles found</p>
          <p className="text-surface-500 text-sm mb-6">
            {searchQuery ? `No results for "${searchQuery}"` : 'No posts in this category yet.'}
          </p>
          <button
            type="button"
            onClick={() => { setActiveCategory('All'); setSearchQuery('') }}
            className="btn-secondary text-sm"
          >
            Clear filters
          </button>
        </div>
      )}

      {/* Featured post */}
      {!loading && featured && (
        <Link
          to={`/blog/${featured.slug}`}
          className="block glass-card overflow-hidden group hover:ring-2 hover:ring-accent-cyan/30 transition-all animate-fade-in"
        >
          <div className="md:flex md:items-stretch">
            {/* Cover */}
            <div className="md:w-64 lg:w-80 shrink-0">
              <CategoryCover category={featured.category} featured />
            </div>
            {/* Content */}
            <div className="flex-1 p-7 md:p-8 flex flex-col justify-between">
              <div>
                <div className="flex flex-wrap items-center gap-2 mb-3">
                  <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded bg-accent-amber/10 text-accent-amber border border-accent-amber/20">
                    Featured
                  </span>
                  <span className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded border ${getCategoryClass(featured.category)}`}>
                    {featured.category}
                  </span>
                </div>
                <h2 className="text-2xl md:text-3xl font-bold text-white group-hover:text-accent-cyan transition-colors leading-tight mb-3">
                  {featured.title}
                </h2>
                <p className="text-surface-400 leading-relaxed line-clamp-3">{featured.excerpt}</p>
              </div>
              <div className="flex flex-wrap items-center justify-between mt-6 gap-4">
                <div className="flex flex-wrap items-center gap-4 text-sm text-surface-500">
                  <span className="flex items-center gap-1"><User size={13} /> {featured.author}</span>
                  <span>{featured.date}</span>
                  <span className="flex items-center gap-1"><Clock size={13} /> {featured.readTime}</span>
                </div>
                <span className="inline-flex items-center gap-1.5 text-accent-cyan text-sm font-semibold group-hover:gap-2.5 transition-all">
                  Read article <ArrowRight size={14} />
                </span>
              </div>
            </div>
          </div>
        </Link>
      )}

      {/* Article grid */}
      {!loading && rest.length > 0 && (
        <div className="animate-slide-up">
          <div className="flex items-center justify-between mb-5">
            <h2 className="text-lg font-semibold text-white flex items-center gap-2">
              {activeCategory === 'All' ? 'All articles' : `${activeCategory} articles`}
              <span className="text-sm font-normal text-surface-500">({rest.length})</span>
            </h2>
          </div>
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            {rest.map(post => (
              <Link
                key={post.slug}
                to={`/blog/${post.slug}`}
                className="glass-card overflow-hidden group hover:ring-1 hover:ring-accent-cyan/20 transition-all flex flex-col h-full"
              >
                {/* Category cover image */}
                <CategoryCover category={post.category} />
                <div className="p-5 flex flex-col flex-1">
                  <span className={`inline-flex self-start text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded border mb-3 ${getCategoryClass(post.category)}`}>
                    {post.category}
                  </span>
                  <h3 className="text-base font-semibold text-white group-hover:text-accent-cyan transition-colors leading-snug mb-2">
                    {post.title}
                  </h3>
                  <p className="text-sm text-surface-400 line-clamp-2 flex-1 leading-relaxed">{post.excerpt}</p>
                  <div className="flex items-center justify-between mt-4 pt-4 border-t border-surface-800/50 text-xs text-surface-500">
                    <span className="flex items-center gap-1"><User size={11} /> {post.author}</span>
                    <span className="flex items-center gap-1">
                      <Clock size={11} /> {post.readTime}
                      <ChevronRight size={13} className="text-surface-600 group-hover:text-accent-cyan group-hover:translate-x-0.5 transition-all ml-1" />
                    </span>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        </div>
      )}

      {/* CTA banner */}
      {!loading && (
        <div className="glass-card p-8 md:p-10 text-center relative overflow-hidden animate-fade-in">
          <div className="absolute inset-0 bg-gradient-to-br from-accent-cyan/8 via-transparent to-accent-purple/8 pointer-events-none" />
          <div className="absolute -top-10 -right-10 w-40 h-40 bg-accent-cyan/5 rounded-full blur-3xl" />
          <div className="relative max-w-xl mx-auto">
            <Sparkles className="text-accent-cyan mx-auto mb-4" size={28} />
            <h2 className="text-xl md:text-2xl font-bold text-white mb-2">Ready to practice?</h2>
            <p className="text-surface-400 text-sm md:text-base mb-6">
              Stop reading docs — break things safely in real Docker, cloud, and simulated environments.
            </p>
            <div className="flex flex-wrap items-center justify-center gap-3">
              <Link to="/register" className="btn-primary px-6 py-2.5 text-sm">Get started free</Link>
              <Link to="/scenarios" className="btn-secondary px-6 py-2.5 text-sm">Browse scenarios</Link>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
