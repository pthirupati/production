import { useState } from 'react'
import PublicLayout from '../components/layout/PublicLayout'
import MarketingPageShell from '../components/MarketingPageShell'
import { FixitPanel } from '../components/design'
import {
  Building2, Send, CheckCircle2, Users, ShieldCheck, Sparkles,
  Mail, ArrowRight,
} from 'lucide-react'
import { Link } from 'react-router-dom'
import toast from 'react-hot-toast'
import api from '../api/client'

const TEAM_SIZES = [
  '1–10',
  '11–50',
  '51–200',
  '201–500',
  '500+',
]

const HIGHLIGHTS = [
  { icon: Users, title: 'Seat licensing', desc: 'Onboard your whole team with centralized billing and seats.' },
  { icon: Sparkles, title: 'Custom pricing', desc: 'A quote tailored to your team size and the technologies you need.' },
  { icon: ShieldCheck, title: 'Priority support', desc: 'Dedicated onboarding and a direct line for your admins.' },
]

const EMPTY = {
  full_name: '',
  organization: '',
  work_email: '',
  company: '',
  phone: '',
  team_size: '',
  message: '',
}

export default function ContactSales() {
  const [form, setForm] = useState(EMPTY)
  const [sending, setSending] = useState(false)
  const [sent, setSent] = useState(false)
  const [errors, setErrors] = useState({})

  const validate = () => {
    const e = {}
    if (!form.full_name.trim()) e.full_name = 'Full name is required'
    if (!form.organization.trim()) e.organization = 'Organization name is required'
    if (!form.work_email.trim()) e.work_email = 'Work email is required'
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.work_email)) e.work_email = 'Enter a valid email'
    if (form.phone && !/^[+\d][\d\s()\-.]{4,}$/.test(form.phone)) e.phone = 'Enter a valid phone number'
    setErrors(e)
    return Object.keys(e).length === 0
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!validate()) return
    setSending(true)
    try {
      const { data } = await api.post('/sales/inquiry/', form)
      toast.success(data.message || 'Thanks! Our team will email you shortly.')
      setForm(EMPTY)
      setSent(true)
    } catch (err) {
      toast.error(err.response?.data?.error || 'Could not submit. Please try again.')
    } finally {
      setSending(false)
    }
  }

  const field = (key) => ({
    value: form[key],
    onChange: (ev) => {
      setForm(prev => ({ ...prev, [key]: ev.target.value }))
      setErrors(prev => ({ ...prev, [key]: '' }))
    },
  })

  return (
    <PublicLayout>
      <MarketingPageShell
        eyebrow="Teams & Organizations"
        title={
          <>
            Bring FixitLab to your{' '}
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-accent-cyan to-accent-blue">
              whole team
            </span>
          </>
        }
        subtitle="Tell us about your organization and we'll put together a custom plan and quote. No fixed pricing — we tailor it to your team."
      >
        <div className="grid lg:grid-cols-5 gap-8 items-start pb-8">
          {/* LEFT: form / success */}
          <div className="lg:col-span-3 animate-slide-up reveal reveal-delay-1">
            {sent ? (
              <FixitPanel padding="p-10" className="flex flex-col items-center justify-center text-center space-y-4 animate-fade-in min-h-[360px]">
                <div className="w-20 h-20 rounded-full bg-accent-green/10 border-2 border-accent-green/30 flex items-center justify-center animate-scale-in">
                  <CheckCircle2 size={40} className="text-accent-green" />
                </div>
                <h3 className="text-xl font-bold text-white">Thanks — we&apos;re on it!</h3>
                <p className="text-surface-400 text-sm max-w-sm">
                  Our team will email you shortly to discuss pricing and the right plan for your organization. We&apos;ve also sent a confirmation to your inbox so you can reply anytime.
                </p>
                <div className="flex flex-wrap items-center justify-center gap-3 mt-2">
                  <button type="button" onClick={() => setSent(false)} className="btn-secondary text-sm">
                    Submit another inquiry
                  </button>
                  <Link to="/pricing" className="btn-primary text-sm inline-flex items-center gap-1">
                    Back to pricing <ArrowRight size={14} />
                  </Link>
                </div>
              </FixitPanel>
            ) : (
              <FixitPanel padding="p-7">
                <form onSubmit={handleSubmit} className="space-y-5">
                  <div className="mb-1 flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-accent-cyan/10 border border-accent-cyan/20 flex items-center justify-center shrink-0">
                      <Building2 size={20} className="text-accent-cyan" />
                    </div>
                    <div>
                      <h2 className="text-xl font-bold text-white">Contact Sales</h2>
                      <p className="text-sm text-surface-400">We typically respond within one business day.</p>
                    </div>
                  </div>

                  <div className="grid sm:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-surface-300 mb-1.5">Full name <span className="text-accent-red">*</span></label>
                      <input
                        type="text"
                        className={`input-field w-full ${errors.full_name ? 'border-accent-red' : ''}`}
                        placeholder="Jane Doe"
                        {...field('full_name')}
                      />
                      {errors.full_name && <p className="text-xs text-accent-red mt-1">{errors.full_name}</p>}
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-surface-300 mb-1.5">Organization name <span className="text-accent-red">*</span></label>
                      <input
                        type="text"
                        className={`input-field w-full ${errors.organization ? 'border-accent-red' : ''}`}
                        placeholder="Acme Inc."
                        {...field('organization')}
                      />
                      {errors.organization && <p className="text-xs text-accent-red mt-1">{errors.organization}</p>}
                    </div>
                  </div>

                  <div className="grid sm:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-surface-300 mb-1.5">Work email <span className="text-accent-red">*</span></label>
                      <input
                        type="email"
                        className={`input-field w-full ${errors.work_email ? 'border-accent-red' : ''}`}
                        placeholder="jane@acme.com"
                        {...field('work_email')}
                      />
                      {errors.work_email && <p className="text-xs text-accent-red mt-1">{errors.work_email}</p>}
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-surface-300 mb-1.5">Company</label>
                      <input
                        type="text"
                        className="input-field w-full"
                        placeholder="Company / billing entity (optional)"
                        {...field('company')}
                      />
                    </div>
                  </div>

                  <div className="grid sm:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-surface-300 mb-1.5">Contact number</label>
                      <input
                        type="tel"
                        className={`input-field w-full ${errors.phone ? 'border-accent-red' : ''}`}
                        placeholder="+1 555 010 1234"
                        {...field('phone')}
                      />
                      {errors.phone && <p className="text-xs text-accent-red mt-1">{errors.phone}</p>}
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-surface-300 mb-1.5">Team size</label>
                      <select className="input-field w-full" {...field('team_size')}>
                        <option value="">Select team size</option>
                        {TEAM_SIZES.map(s => (
                          <option key={s} value={s}>{s} people</option>
                        ))}
                      </select>
                    </div>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-surface-300 mb-1.5">Other details / message</label>
                    <textarea
                      className="input-field w-full h-32 resize-none"
                      placeholder="Which technologies are you interested in? Any timeline, seat count, or requirements?"
                      {...field('message')}
                    />
                  </div>

                  <button
                    type="submit"
                    disabled={sending}
                    className="btn-primary w-full flex items-center justify-center gap-2 py-3 text-base disabled:opacity-50"
                  >
                    <Send size={16} />
                    {sending ? 'Sending...' : 'Request a quote'}
                  </button>
                  <p className="text-center text-xs text-surface-500">
                    By submitting, you agree to be contacted by FixitLab about your inquiry.
                  </p>
                </form>
              </FixitPanel>
            )}
          </div>

          {/* RIGHT: highlights */}
          <div className="lg:col-span-2 space-y-5 animate-slide-up reveal reveal-delay-2">
            <FixitPanel padding="p-6" className="border border-accent-cyan/20 bg-gradient-to-br from-accent-cyan/5 to-transparent">
              <h3 className="text-base font-bold text-white mb-1">Why teams choose FixitLab</h3>
              <p className="text-sm text-surface-400 mb-5">Hands-on labs and AI interviews, licensed for your org.</p>
              <div className="space-y-4">
                {HIGHLIGHTS.map(({ icon: Icon, title, desc }) => (
                  <div key={title} className="flex items-start gap-3">
                    <div className="w-9 h-9 rounded-lg bg-accent-cyan/10 border border-accent-cyan/20 flex items-center justify-center shrink-0">
                      <Icon size={18} className="text-accent-cyan" />
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-white">{title}</p>
                      <p className="text-xs text-surface-400 leading-relaxed">{desc}</p>
                    </div>
                  </div>
                ))}
              </div>
            </FixitPanel>

            <FixitPanel padding="p-5" className="flex items-center gap-4">
              <div className="w-11 h-11 rounded-xl bg-accent-purple/10 border border-accent-purple/20 flex items-center justify-center shrink-0">
                <Mail size={20} className="text-accent-purple" />
              </div>
              <div className="min-w-0">
                <p className="text-xs text-surface-500 uppercase tracking-wide font-medium mb-0.5">Prefer email?</p>
                <a href="mailto:fixitlab.admin@gmail.com" className="text-sm font-medium text-accent-purple truncate hover:underline">
                  fixitlab.admin@gmail.com
                </a>
              </div>
            </FixitPanel>
          </div>
        </div>
      </MarketingPageShell>
    </PublicLayout>
  )
}
