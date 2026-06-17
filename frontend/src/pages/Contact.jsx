import { useState } from 'react'
import PublicLayout from '../components/layout/PublicLayout'
import { Mail, Phone, MapPin, Send, MessageCircle, Mic, Clock, Twitter, Github, ArrowRight } from 'lucide-react'
import { Link } from 'react-router-dom'
import toast from 'react-hot-toast'
import api from '../api/client'

const SUBJECT_PRESETS = [
  { label: 'General support',              value: 'General support' },
  { label: 'Interview Studio / mock interviews', value: 'Interview Studio support' },
  { label: 'Billing & subscriptions',      value: 'Billing question' },
  { label: 'Interview billing / refunds',  value: 'Interview plan billing' },
  { label: 'Certificate verification',     value: 'Certificate verification' },
]

const CONTACT_CARDS = [
  {
    icon: Mail,
    label: 'General',
    value: 'fixitlab@gmail.com',
    href: 'mailto:fixitlab.admin@gmail.com',
    color: 'text-accent-cyan',
    bg: 'bg-accent-cyan/10',
    border: 'border-accent-cyan/20',
  },
  {
    icon: Phone,
    label: 'Tech support',
    value: 'fixitlab.techsupport@gmail.com',
    href: 'mailto:fixitlab.techsupport@gmail.com',
    color: 'text-accent-green',
    bg: 'bg-accent-green/10',
    border: 'border-accent-green/20',
  },
  {
    icon: Mic,
    label: 'Interview Studio',
    value: 'Interview support',
    href: 'mailto:fixitlab.techsupport@gmail.com?subject=Interview%20Studio',
    color: 'text-accent-purple',
    bg: 'bg-accent-purple/10',
    border: 'border-accent-purple/20',
  },
  {
    icon: MapPin,
    label: 'Payments',
    value: 'fixitlab.payment@gmail.com',
    href: 'mailto:fixitlab.payment@gmail.com',
    color: 'text-accent-amber',
    bg: 'bg-accent-amber/10',
    border: 'border-accent-amber/20',
  },
]

export default function Contact() {
  const [form, setForm] = useState({ name: '', email: '', subject: '', message: '' })
  const [sending, setSending] = useState(false)
  const [errors, setErrors] = useState({})

  const validate = () => {
    const e = {}
    if (!form.name.trim()) e.name = 'Name is required'
    if (!form.email.trim()) e.email = 'Email is required'
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)) e.email = 'Invalid email format'
    if (!form.subject.trim()) e.subject = 'Subject is required'
    if (!form.message.trim()) e.message = 'Message is required'
    else if (form.message.trim().length < 10) e.message = 'Message must be at least 10 characters'
    setErrors(e)
    return Object.keys(e).length === 0
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!validate()) return
    setSending(true)
    try {
      const { data } = await api.post('/contact/', form)
      toast.success(data.message || "Message sent! We'll get back to you within 24 hours.")
      setForm({ name: '', email: '', subject: '', message: '' })
    } catch (err) {
      toast.error(err.response?.data?.error || 'Failed to send message. Please try again.')
    } finally {
      setSending(false)
    }
  }

  const field = (key) => ({
    value: form[key],
    onChange: (e) => {
      setForm(prev => ({ ...prev, [key]: e.target.value }))
      setErrors(prev => ({ ...prev, [key]: '' }))
    },
  })

  return (
    <PublicLayout>
      {/* ── Hero ──────────────────────────────────────────────── */}
      <section className="relative overflow-hidden py-20">
        <div className="absolute inset-0 hero-grid opacity-40 pointer-events-none" />
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[700px] h-[400px] bg-accent-cyan/6 rounded-full blur-3xl pointer-events-none" />

        <div className="max-w-3xl mx-auto px-6 text-center relative animate-fade-in">
          <div className="w-16 h-16 mx-auto mb-6 rounded-2xl bg-gradient-to-br from-accent-cyan/20 to-accent-blue/20 border border-accent-cyan/20 flex items-center justify-center">
            <MessageCircle size={30} className="text-accent-cyan" />
          </div>
          <h1 className="text-5xl font-extrabold text-white mb-3 tracking-tight">
            Get in{' '}
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-accent-cyan to-accent-blue">
              Touch
            </span>
          </h1>
          <p className="text-surface-400 text-lg">Labs, interviews, billing — we're here to help.</p>
        </div>
      </section>

      {/* ── Interview Studio banner ────────────────────────────── */}
      <div className="max-w-6xl mx-auto px-6 mb-8">
        <div className="glass-card p-4 border border-accent-purple/20 flex flex-col sm:flex-row sm:items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-accent-purple/10 border border-accent-purple/20 flex items-center justify-center shrink-0">
            <Mic size={18} className="text-accent-purple" />
          </div>
          <div className="flex-1">
            <p className="text-sm font-medium text-white">AI Interview Studio</p>
            <p className="text-xs text-surface-500">Questions about mock interviews, voice, certificates (FIXIT-INT), or interview plans.</p>
          </div>
          <Link to="/mock-interviews" className="text-xs text-accent-purple hover:text-accent-purple/80 inline-flex items-center gap-1 whitespace-nowrap transition-colors">
            Learn more <ArrowRight size={12} />
          </Link>
        </div>
      </div>

      {/* ── Main two-column layout ─────────────────────────────── */}
      <div className="max-w-6xl mx-auto px-6 pb-24">
        <div className="grid lg:grid-cols-5 gap-8 items-start">

          {/* ── LEFT: Contact form ─────────────────────────────── */}
          <div className="lg:col-span-3 animate-slide-up">
            <form onSubmit={handleSubmit} className="glass-card p-7 space-y-5">
              <div className="mb-1">
                <h2 className="text-xl font-bold text-white mb-1">Send us a message</h2>
                <p className="text-sm text-surface-400">We typically respond within 24 hours.</p>
              </div>

              {/* Name + Email row */}
              <div className="grid sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-surface-300 mb-1.5">Name</label>
                  <input
                    type="text"
                    className={`input-field w-full ${errors.name ? 'border-accent-red' : ''}`}
                    placeholder="Your name"
                    {...field('name')}
                    required
                  />
                  {errors.name && <p className="text-xs text-accent-red mt-1">{errors.name}</p>}
                </div>
                <div>
                  <label className="block text-sm font-medium text-surface-300 mb-1.5">Email</label>
                  <input
                    type="email"
                    className={`input-field w-full ${errors.email ? 'border-accent-red' : ''}`}
                    placeholder="you@example.com"
                    {...field('email')}
                    required
                  />
                  {errors.email && <p className="text-xs text-accent-red mt-1">{errors.email}</p>}
                </div>
              </div>

              {/* Subject */}
              <div>
                <label className="block text-sm font-medium text-surface-300 mb-1.5">Subject</label>
                {/* Quick-pick chips */}
                <div className="flex flex-wrap gap-1.5 mb-2">
                  {SUBJECT_PRESETS.map(p => (
                    <button
                      key={p.value}
                      type="button"
                      onClick={() => setForm(prev => ({ ...prev, subject: p.value }))}
                      className={`text-[11px] px-2.5 py-1 rounded-lg border transition-colors ${
                        form.subject === p.value
                          ? 'border-accent-cyan/50 bg-accent-cyan/10 text-accent-cyan'
                          : 'border-surface-700 text-surface-400 hover:border-surface-500 hover:text-surface-200'
                      }`}
                    >
                      {p.label}
                    </button>
                  ))}
                </div>
                <input
                  type="text"
                  className={`input-field w-full ${errors.subject ? 'border-accent-red' : ''}`}
                  placeholder="Or type a custom subject"
                  {...field('subject')}
                  required
                />
                {errors.subject && <p className="text-xs text-accent-red mt-1">{errors.subject}</p>}
              </div>

              {/* Message */}
              <div>
                <label className="block text-sm font-medium text-surface-300 mb-1.5">Message</label>
                <textarea
                  className={`input-field w-full h-40 resize-none ${errors.message ? 'border-accent-red' : ''}`}
                  placeholder="Describe your issue or question..."
                  {...field('message')}
                  required
                />
                {errors.message && <p className="text-xs text-accent-red mt-1">{errors.message}</p>}
              </div>

              <button
                type="submit"
                disabled={sending}
                className="btn-primary w-full flex items-center justify-center gap-2 py-3 text-base"
              >
                <Send size={16} />
                {sending ? 'Sending...' : 'Send Message'}
              </button>
            </form>
          </div>

          {/* ── RIGHT: Contact info ────────────────────────────── */}
          <div className="lg:col-span-2 space-y-5 animate-slide-up" style={{ animationDelay: '100ms' }}>
            <div>
              <h2 className="text-xl font-bold text-white mb-1">Contact info</h2>
              <p className="text-sm text-surface-400">Reach us directly via email.</p>
            </div>

            {/* Contact cards */}
            {CONTACT_CARDS.map(({ icon: Icon, label, value, href, color, bg, border }) => (
              <a
                key={label}
                href={href}
                className={`glass-card-hover p-5 flex items-center gap-4 group block`}
              >
                <div className={`w-11 h-11 rounded-xl ${bg} border ${border} flex items-center justify-center shrink-0 group-hover:scale-110 transition-transform`}>
                  <Icon size={20} className={color} />
                </div>
                <div className="min-w-0">
                  <p className="text-xs text-surface-500 uppercase tracking-wide font-medium mb-0.5">{label}</p>
                  <p className={`text-sm font-medium ${color} truncate`}>{value}</p>
                </div>
              </a>
            ))}

            {/* Support hours */}
            <div className="glass-card p-5 flex items-start gap-4">
              <div className="w-11 h-11 rounded-xl bg-accent-blue/10 border border-accent-blue/20 flex items-center justify-center shrink-0">
                <Clock size={20} className="text-accent-blue" />
              </div>
              <div>
                <p className="text-xs text-surface-500 uppercase tracking-wide font-medium mb-1">Support hours</p>
                <p className="text-sm text-surface-200 font-medium">Mon–Fri, 9 AM – 6 PM IST</p>
                <p className="text-xs text-surface-500 mt-0.5">Typical response within 24 hours</p>
              </div>
            </div>

            {/* Social links */}
            <div className="glass-card p-5">
              <p className="text-xs text-surface-500 uppercase tracking-wide font-medium mb-3">Follow us</p>
              <div className="flex items-center gap-3">
                <a
                  href="https://twitter.com/fixitlab"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-2 text-sm text-surface-400 hover:text-accent-cyan transition-colors"
                >
                  <Twitter size={16} /> Twitter
                </a>
                <span className="text-surface-700">·</span>
                <a
                  href="https://github.com/fixitlab"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-2 text-sm text-surface-400 hover:text-accent-cyan transition-colors"
                >
                  <Github size={16} /> GitHub
                </a>
              </div>
            </div>
          </div>
        </div>
      </div>
    </PublicLayout>
  )
}
