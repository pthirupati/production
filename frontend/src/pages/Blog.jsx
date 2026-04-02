import { Link } from 'react-router-dom'
import { Terminal, Clock, ArrowRight, Tag, User, ChevronRight } from 'lucide-react'

const posts = [
  {
    slug: 'why-hands-on-learning-works',
    title: 'Why Hands-On Learning Works Better Than Reading Docs',
    excerpt: 'Studies show engineers retain 75% of what they practice compared to 10% of what they read. Here is how FixitLab applies this to hands-on technology training.',
    category: 'Education',
    author: 'Thirupathi P.',
    date: 'March 28, 2026',
    readTime: '5 min read',
    color: 'accent-cyan',
    featured: true,
  },
  {
    slug: 'debugging-nginx-like-a-pro',
    title: 'Debugging Nginx Like a Pro: A Step-by-Step Guide',
    excerpt: 'Learn the systematic approach SREs use to diagnose Nginx configuration issues — from error logs to config validation to upstream debugging.',
    category: 'Linux',
    author: 'Platform Team',
    date: 'March 25, 2026',
    readTime: '8 min read',
    color: 'accent-green',
  },
  {
    slug: 'docker-vs-cloud-labs',
    title: 'Docker vs Cloud Labs: When to Use Each for Training',
    excerpt: 'FixitLab supports Docker containers, AWS EC2, and DigitalOcean droplets. Here is when and why we use each provider for different scenarios.',
    category: 'Architecture',
    author: 'Platform Team',
    date: 'March 22, 2026',
    readTime: '6 min read',
    color: 'accent-purple',
  },
  {
    slug: 'top-5-linux-troubleshooting-commands',
    title: 'Top 5 Linux Commands Every SRE Should Master',
    excerpt: 'From strace to ss to journalctl — these five commands will save you hours during incident response. With practical examples and scenarios.',
    category: 'Linux',
    author: 'Content Team',
    date: 'March 18, 2026',
    readTime: '7 min read',
    color: 'accent-amber',
  },
  {
    slug: 'building-fixitlab-architecture',
    title: 'How We Built FixitLab: Architecture Deep Dive',
    excerpt: 'A look behind the scenes at FixitLab\'s architecture — Django, React, WebSockets, Docker SDK, Celery, and how we handle 1000+ concurrent labs.',
    category: 'Engineering',
    author: 'Thirupathi P.',
    date: 'March 15, 2026',
    readTime: '12 min read',
    color: 'accent-cyan',
  },
  {
    slug: 'dns-troubleshooting-guide',
    title: 'DNS Resolution Failures: A Complete Troubleshooting Playbook',
    excerpt: 'DNS is the #1 cause of outages. Learn to debug /etc/resolv.conf, nsswitch.conf, dig/nslookup failures, and more.',
    category: 'Networking',
    author: 'Content Team',
    date: 'March 10, 2026',
    readTime: '9 min read',
    color: 'accent-green',
  },
]

export default function Blog() {
  const featured = posts.find(p => p.featured)
  const rest = posts.filter(p => !p.featured)

  return (
    <div className="min-h-screen bg-surface-950">
      {/* Nav */}
      <nav className="border-b border-surface-800/50 backdrop-blur-xl sticky top-0 z-50 bg-surface-950/90">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-accent-cyan to-brand-600 flex items-center justify-center shadow-lg shadow-accent-cyan/20">
              <Terminal size={18} className="text-white" />
            </div>
            <span className="text-xl font-bold text-white tracking-tight">FixitLab</span>
          </Link>
          <div className="hidden md:flex items-center gap-6">
            <Link to="/scenarios" className="text-sm text-surface-400 hover:text-white transition-colors">Scenarios</Link>
            <Link to="/pricing" className="text-sm text-surface-400 hover:text-white transition-colors">Pricing</Link>
            <Link to="/blog" className="text-sm text-white font-medium">Blog</Link>
            <Link to="/about" className="text-sm text-surface-400 hover:text-white transition-colors">About</Link>
          </div>
          <Link to="/register" className="btn-primary text-sm px-5">Get Started Free</Link>
        </div>
      </nav>

      {/* Header */}
      <section className="relative overflow-hidden">
        <div className="absolute inset-0">
          <div className="absolute inset-0 opacity-[0.03]"
            style={{ backgroundImage: 'linear-gradient(rgb(var(--a-cyan)) 1px, transparent 1px), linear-gradient(90deg, rgb(var(--a-cyan)) 1px, transparent 1px)', backgroundSize: '60px 60px' }} />
          <div className="absolute top-0 right-1/4 w-[600px] h-[400px] bg-accent-cyan/5 rounded-full blur-3xl" />
        </div>
        <div className="max-w-5xl mx-auto px-6 pt-16 pb-12 text-center relative">
          <h1 className="text-4xl lg:text-5xl font-extrabold text-white mb-4">Engineering Blog</h1>
          <p className="text-lg text-surface-400 max-w-xl mx-auto">
            Tutorials, architecture deep-dives, and troubleshooting guides from the FixitLab team.
          </p>
        </div>
      </section>

      <div className="max-w-6xl mx-auto px-6 pb-20">
        {/* Featured Post */}
        {featured && (
          <div className="mb-12">
            <Link to={`/blog/${featured.slug}`} className="glass-card-hover overflow-hidden group block">
              <div className="grid md:grid-cols-2">
                {/* Image area */}
                <div className={`bg-gradient-to-br from-${featured.color}/20 to-surface-900 p-8 md:p-12 flex items-center justify-center relative overflow-hidden`}>
                  <div className="absolute inset-0 opacity-[0.06]"
                    style={{ backgroundImage: 'linear-gradient(rgb(var(--a-cyan)) 1px, transparent 1px), linear-gradient(90deg, rgb(var(--a-cyan)) 1px, transparent 1px)', backgroundSize: '20px 20px' }} />
                  <div className="relative text-center">
                    <div className="w-24 h-24 rounded-2xl bg-surface-800/50 border border-surface-700/50 flex items-center justify-center mx-auto mb-4 group-hover:scale-110 transition-transform">
                      <Terminal size={40} className={`text-${featured.color}`} />
                    </div>
                    <span className="badge bg-accent-cyan/10 text-accent-cyan border border-accent-cyan/20">Featured</span>
                  </div>
                </div>
                {/* Content */}
                <div className="p-8 md:p-10 flex flex-col justify-center">
                  <div className="flex items-center gap-3 mb-3">
                    <span className={`badge bg-${featured.color}/10 text-${featured.color} border border-${featured.color}/20`}>
                      <Tag size={10} className="mr-1" />{featured.category}
                    </span>
                    <span className="text-xs text-surface-500 flex items-center gap-1"><Clock size={10} />{featured.readTime}</span>
                  </div>
                  <h2 className="text-2xl font-bold text-white mb-3 group-hover:text-accent-cyan transition-colors">{featured.title}</h2>
                  <p className="text-surface-400 text-sm leading-relaxed mb-4">{featured.excerpt}</p>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 text-xs text-surface-500">
                      <User size={12} /> {featured.author} &middot; {featured.date}
                    </div>
                    <span className="text-accent-cyan text-sm font-medium flex items-center gap-1 group-hover:gap-2 transition-all">
                      Read more <ArrowRight size={14} />
                    </span>
                  </div>
                </div>
              </div>
            </Link>
          </div>
        )}

        {/* Post Grid */}
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
          {rest.map((post) => (
            <Link to={`/blog/${post.slug}`} key={post.slug} className="glass-card-hover overflow-hidden group flex flex-col">
              {/* Colored header area */}
              <div className={`h-40 bg-gradient-to-br from-${post.color}/10 via-surface-900 to-surface-900 relative overflow-hidden flex items-center justify-center`}>
                <div className="absolute inset-0 opacity-[0.06]"
                  style={{ backgroundImage: `radial-gradient(rgb(var(--a-cyan)) 1px, transparent 1px)`, backgroundSize: '20px 20px' }} />
                <Terminal size={48} className={`text-${post.color}/30 group-hover:text-${post.color}/50 transition-colors`} />
              </div>
              {/* Content */}
              <div className="p-5 flex flex-col flex-1">
                <div className="flex items-center gap-2 mb-2">
                  <span className={`text-[10px] font-bold uppercase tracking-wider text-${post.color}`}>{post.category}</span>
                  <span className="text-surface-700">&middot;</span>
                  <span className="text-[10px] text-surface-500">{post.readTime}</span>
                </div>
                <h3 className="text-lg font-semibold text-white mb-2 leading-snug group-hover:text-accent-cyan transition-colors">{post.title}</h3>
                <p className="text-sm text-surface-400 leading-relaxed flex-1">{post.excerpt}</p>
                <div className="flex items-center justify-between mt-4 pt-3 border-t border-surface-800/50">
                  <div className="text-xs text-surface-500">{post.date}</div>
                  <span className="text-xs text-accent-cyan font-medium flex items-center gap-1 group-hover:gap-2 transition-all">
                    Read <ChevronRight size={12} />
                  </span>
                </div>
              </div>
            </Link>
          ))}
        </div>

        {/* Newsletter CTA */}
        <div className="mt-16 glass-card p-8 md:p-12 text-center relative overflow-hidden">
          <div className="absolute inset-0 bg-gradient-to-br from-accent-cyan/5 to-accent-purple/5" />
          <div className="relative">
            <h2 className="text-2xl font-bold text-white mb-2">Stay in the loop</h2>
            <p className="text-surface-400 mb-6 max-w-md mx-auto text-sm">
              Get new tutorials and troubleshooting guides delivered to your inbox. No spam.
            </p>
            <div className="flex flex-col sm:flex-row gap-3 max-w-md mx-auto">
              <input
                type="email"
                placeholder="your@email.com"
                className="input-field flex-1 text-sm"
              />
              <button className="btn-primary px-6 text-sm whitespace-nowrap">Subscribe</button>
            </div>
          </div>
        </div>
      </div>

      {/* Footer */}
      <footer className="border-t border-surface-800/50 bg-surface-900/30">
        <div className="max-w-7xl mx-auto px-6 py-8 flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-accent-cyan to-brand-600 flex items-center justify-center">
              <Terminal size={14} className="text-white" />
            </div>
            <span className="text-sm font-bold text-white">FixitLab</span>
          </div>
          <p className="text-xs text-surface-600">&copy; 2026 FixitLab. All rights reserved.</p>
        </div>
      </footer>
    </div>
  )
}
