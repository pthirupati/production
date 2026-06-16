import PublicLayout from '../components/layout/PublicLayout'
import { Shield, Lock, Eye, Database, UserCheck, FileText, ExternalLink } from 'lucide-react'

export default function Privacy() {
  const sections = [
    {
      icon: Eye,
      title: 'Information We Collect',
      color: 'from-cyan-500 to-blue-600',
      items: [
        'Your name, email address, phone number, and location',
        'Username and profile information you choose to provide',
        'Lab session activity, including commands entered and results',
        'Resume uploads and parsed career data for AI Interview Studio',
        'Interview transcripts, scores, and session metadata from mock interviews',
        'Camera and microphone status during interviews (not stored as video by default)',
        'Browser speech recognition text when you use voice answers',
        'Subscription and payment information (processed securely)',
        'Browser type, IP address, and device information for security',
      ],
    },
    {
      icon: Database,
      title: 'How We Use Your Data',
      color: 'from-green-500 to-emerald-600',
      items: [
        'To provide and improve our platform services',
        'To personalize your learning experience and tailor interview questions',
        'To run AI mock interviews using our own rule-based engine (no third-party LLM APIs)',
        'To process voice answers via your browser\'s Speech API (audio stays on your device)',
        'To process payments and manage subscriptions',
        'To send important account notifications',
        'To analyze platform usage and improve features',
        'To prevent abuse and maintain platform security',
      ],
    },
    {
      icon: Lock,
      title: 'Data Security',
      color: 'from-amber-500 to-orange-600',
      text: 'We implement industry-standard security measures including encrypted data transmission (TLS), hashed passwords, secure authentication tokens, and regular security audits to protect your data. Lab sessions are isolated in sandboxed containers that are destroyed after use.',
    },
    {
      icon: UserCheck,
      title: 'Your Rights',
      color: 'from-purple-500 to-violet-600',
      items: [
        'Access and download your personal data',
        'Request correction of inaccurate data',
        'Request deletion of your account and data',
        'Opt out of marketing communications via email unsubscribe link or Profile settings',
        'Export your lab history and progress data',
        'Request deletion of interview resumes, transcripts, and reports',
        'Accounts without any subscription for 3 months may be deleted after a warning email — all data is removed from our database',
      ],
    },
  ]

  return (
    <PublicLayout>
      <div className="relative overflow-hidden">
        {/* Decorative background */}
        <div className="absolute inset-0 pointer-events-none">
          <div className="absolute top-32 right-1/4 w-80 h-80 bg-accent-green/5 rounded-full blur-3xl" />
          <div className="absolute bottom-20 left-1/3 w-96 h-96 bg-accent-purple/5 rounded-full blur-3xl" />
        </div>

        <div className="max-w-4xl mx-auto px-4 py-16 relative">
          {/* Hero */}
          <div className="text-center mb-16 animate-fade-in">
            <div className="w-20 h-20 mx-auto mb-6 rounded-2xl bg-gradient-to-br from-green-500/20 to-cyan-500/20 border border-green-500/20 flex items-center justify-center">
              <Shield size={36} className="text-accent-green" />
            </div>
            <h1 className="text-5xl font-extrabold mb-4 bg-gradient-to-r from-white via-green-300 to-cyan-400 bg-clip-text text-transparent">
              Privacy Policy
            </h1>
            <p className="text-surface-400 text-lg">Last updated: June 5, 2026</p>
            <div className="w-20 h-1 bg-gradient-to-r from-accent-green to-accent-cyan rounded-full mx-auto mt-6" />
          </div>

          {/* Sections */}
          <div className="space-y-6">
            {sections.map((section, i) => {
              const Icon = section.icon
              return (
                <section
                  key={i}
                  className="glass-card p-8 hover:border-accent-green/20 transition-all duration-300 animate-fade-in"
                  style={{ animationDelay: `${i * 0.1}s` }}
                >
                  <div className="flex items-center gap-4 mb-5">
                    <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${section.color} flex items-center justify-center shadow-lg`}>
                      <Icon size={20} className="text-white" />
                    </div>
                    <h2 className="text-xl font-bold text-white">{section.title}</h2>
                  </div>
                  {section.text && (
                    <p className="text-surface-300 leading-relaxed">{section.text}</p>
                  )}
                  {section.items && (
                    <ul className="space-y-2">
                      {section.items.map((item, j) => (
                        <li key={j} className="flex items-start gap-3 text-surface-300">
                          <span className="w-1.5 h-1.5 rounded-full bg-accent-green mt-2 shrink-0" />
                          <span className="leading-relaxed">{item}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                </section>
              )
            })}

            {/* Interview Studio */}
            <section className="glass-card p-8 border-indigo-500/20 animate-fade-in">
              <h2 className="text-xl font-bold text-white mb-4">AI Interview Studio</h2>
              <ul className="space-y-2 text-surface-300 text-sm">
                <li>Mock interviews require camera and microphone; you must consent before each session.</li>
                <li>We store text transcripts and scores. Video is not recorded on our servers unless explicitly stated.</li>
                <li>Voice uses your browser&apos;s built-in speech APIs — no paid third-party TTS/STT services.</li>
                <li>Admins may request to observe a live session; you must approve before they can view the transcript.</li>
                <li>Interview data is retained while your account is active and deleted with account deletion requests.</li>
              </ul>
            </section>

            {/* Contact */}
            <section className="glass-card p-8 border-accent-green/20 bg-gradient-to-br from-accent-green/5 to-transparent animate-fade-in">
              <div className="flex items-center gap-4 mb-5">
                <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center shadow-lg">
                  <FileText size={20} className="text-white" />
                </div>
                <h2 className="text-xl font-bold text-white">Contact</h2>
              </div>
              <p className="text-surface-300 leading-relaxed">
                For privacy-related inquiries, please contact us at{' '}
                <a href="mailto:fixitlab.admin@gmail.com" className="inline-flex items-center gap-1 text-accent-cyan hover:underline font-medium">
                  fixitlab.admin@gmail.com <ExternalLink size={12} />
                </a>
              </p>
            </section>
          </div>
        </div>
      </div>
    </PublicLayout>
  )
}
