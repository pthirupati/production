import { useState } from 'react'
import PublicLayout from '../components/layout/PublicLayout'
import { Mail, Phone, MapPin, Send, MessageCircle } from 'lucide-react'
import toast from 'react-hot-toast'
import api from '../api/client'

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
      toast.success(data.message || 'Message sent! We\'ll get back to you within 24 hours.')
      setForm({ name: '', email: '', subject: '', message: '' })
    } catch (err) {
      toast.error(err.response?.data?.error || 'Failed to send message. Please try again.')
    } finally {
      setSending(false)
    }
  }

  return (
    <PublicLayout>
      <div className="max-w-6xl mx-auto px-4 py-16">
        <div className="text-center mb-12">
          <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-gradient-to-br from-cyan-500/20 to-blue-500/20 flex items-center justify-center">
            <MessageCircle size={32} className="text-cyan-400" />
          </div>
          <h1 className="text-4xl font-bold mb-2">Contact Us</h1>
          <p className="text-surface-400">We'd love to hear from you. Get in touch with our team.</p>
        </div>

        <div className="grid md:grid-cols-3 gap-8">
          {/* Contact Info Cards */}
          <div className="space-y-4">
            <div className="glass-card p-6 text-center">
              <Mail size={24} className="text-cyan-400 mx-auto mb-3" />
              <h3 className="font-semibold mb-1">Email</h3>
              <a href="mailto:fixitlab.admin@gmail.com" className="text-sm text-cyan-400 hover:underline">
                fixitlab@gmail.com
              </a>
            </div>
            <div className="glass-card p-6 text-center">
              <Phone size={24} className="text-cyan-400 mx-auto mb-3" />
              <h3 className="font-semibold mb-1">Support</h3>
              <a href="mailto:fixitlab.techsupport@gmail.com" className="text-sm text-cyan-400 hover:underline">
                fixitlab.techsupport@gmail.com
              </a>
            </div>
            <div className="glass-card p-6 text-center">
              <MapPin size={24} className="text-cyan-400 mx-auto mb-3" />
              <h3 className="font-semibold mb-1">Payments</h3>
              <a href="mailto:fixitlab.payment@gmail.com" className="text-sm text-cyan-400 hover:underline">
                fixitlab.payment@gmail.com
              </a>
            </div>
          </div>

          {/* Contact Form */}
          <div className="md:col-span-2">
            <form onSubmit={handleSubmit} className="glass-card p-6 space-y-4">
              <div className="grid sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium mb-1">Name</label>
                  <input
                    type="text"
                    className={`input-field w-full ${errors.name ? 'border-accent-red' : ''}`}
                    value={form.name}
                    onChange={(e) => { setForm({ ...form, name: e.target.value }); setErrors(prev => ({ ...prev, name: '' })) }}
                    required
                  />
                  {errors.name && <p className="text-xs text-accent-red mt-1">{errors.name}</p>}
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">Email</label>
                  <input
                    type="email"
                    className={`input-field w-full ${errors.email ? 'border-accent-red' : ''}`}
                    value={form.email}
                    onChange={(e) => { setForm({ ...form, email: e.target.value }); setErrors(prev => ({ ...prev, email: '' })) }}
                    required
                  />
                  {errors.email && <p className="text-xs text-accent-red mt-1">{errors.email}</p>}
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Subject</label>
                <input
                  type="text"
                  className={`input-field w-full ${errors.subject ? 'border-accent-red' : ''}`}
                  value={form.subject}
                  onChange={(e) => { setForm({ ...form, subject: e.target.value }); setErrors(prev => ({ ...prev, subject: '' })) }}
                  required
                />
                {errors.subject && <p className="text-xs text-accent-red mt-1">{errors.subject}</p>}
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Message</label>
                <textarea
                  className={`input-field w-full h-40 resize-none ${errors.message ? 'border-accent-red' : ''}`}
                  value={form.message}
                  onChange={(e) => { setForm({ ...form, message: e.target.value }); setErrors(prev => ({ ...prev, message: '' })) }}
                  required
                />
                {errors.message && <p className="text-xs text-accent-red mt-1">{errors.message}</p>}
              </div>
              <button
                type="submit"
                disabled={sending}
                className="btn-primary w-full flex items-center justify-center gap-2"
              >
                <Send size={16} />
                {sending ? 'Sending...' : 'Send Message'}
              </button>
            </form>
          </div>
        </div>
      </div>
    </PublicLayout>
  )
}
