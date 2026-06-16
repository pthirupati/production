import PublicLayout from '../components/layout/PublicLayout'
import { ScrollText, AlertCircle, CreditCard, UserX, Scale, Shield, ExternalLink } from 'lucide-react'

export default function Terms() {
  const sections = [
    {
      icon: Scale,
      title: '1. Acceptance of Terms',
      color: 'from-cyan-500 to-blue-600',
      content: (
        <p className="text-surface-300 leading-relaxed">
          By accessing or using FixitLab, you agree to be bound by these Terms of Service. If you do not
          agree to these terms, please do not use our platform. FixitLab reserves the right to modify
          these terms at any time with notice to users.
        </p>
      ),
    },
    {
      icon: Shield,
      title: '2. Use of Service',
      color: 'from-green-500 to-emerald-600',
      content: (
        <>
          <p className="text-surface-300 mb-3 leading-relaxed">You agree to:</p>
          <ul className="space-y-2">
            {[
              'Use the platform only for its intended educational purpose',
              'Not attempt to access other users\' data or lab environments',
              'Not use the platform for any malicious, illegal, or harmful activity',
              'Not attempt to circumvent security measures or access controls',
              'Not share your account credentials with others',
              'Comply with all applicable laws and regulations',
            ].map((item, i) => (
              <li key={i} className="flex items-start gap-3 text-surface-300">
                <span className="w-1.5 h-1.5 rounded-full bg-accent-cyan mt-2 shrink-0" />
                <span className="leading-relaxed">{item}</span>
              </li>
            ))}
          </ul>
        </>
      ),
    },
    {
      icon: CreditCard,
      title: '3. Subscriptions & Payments',
      color: 'from-amber-500 to-orange-600',
      content: (
        <ul className="space-y-2">
          {[
            'Technology subscriptions grant 1-year access to specific technology content',
            'Interview Studio plans (Pro/Premium) include 10 attempts per year with 1-year validity',
            'Payments are processed by Razorpay (INR) or Stripe (USD) — card, UPI, net banking, and wallet',
            'Bank OTP, 3D Secure, and UPI authentication are handled entirely by the payment gateway',
            'FixitLab never stores your card number, CVV, or UPI PIN — only payment confirmation IDs',
            'Refund requests must be made within 7 days of purchase',
            'We reserve the right to modify pricing with 30 days notice',
          ].map((item, i) => (
            <li key={i} className="flex items-start gap-3 text-surface-300">
              <span className="w-1.5 h-1.5 rounded-full bg-accent-amber mt-2 shrink-0" />
              <span className="leading-relaxed">{item}</span>
            </li>
          ))}
        </ul>
      ),
    },
    {
      icon: AlertCircle,
      title: '4. AI Interview Studio',
      color: 'from-indigo-500 to-purple-600',
      content: (
        <ul className="space-y-2">
          {[
            'Interview sessions require a working camera and microphone throughout the round',
            'A 5-minute grace period applies if AV is disabled; the session may end automatically after that',
            'You consent to transcript storage and AI scoring when you start an interview',
            'Voice features use your browser — FixitLab does not provide human interviewers',
            'Admin observers may join only with your explicit approval during a live session',
            'Interview certificates (FIXIT-INT) are issued only after passing all campaign rounds',
            'Complimentary or admin-granted free access may be revoked at our discretion',
          ].map((item, i) => (
            <li key={i} className="flex items-start gap-3 text-surface-300">
              <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 mt-2 shrink-0" />
              <span className="leading-relaxed">{item}</span>
            </li>
          ))}
        </ul>
      ),
    },
    {
      icon: AlertCircle,
      title: '5. Content & Intellectual Property',
      color: 'from-purple-500 to-violet-600',
      content: (
        <p className="text-surface-300 leading-relaxed">
          All scenarios, lab content, and platform materials are the intellectual property of FixitLab.
          Community-contributed content (threads, replies) remains the property of the author but
          FixitLab retains the right to display and moderate such content.
        </p>
      ),
    },
    {
      icon: UserX,
      title: '6. Account Termination',
      color: 'from-red-500 to-rose-600',
      content: (
        <>
          <p className="text-surface-300 leading-relaxed mb-3">
            We reserve the right to suspend or terminate accounts that violate these terms or engage in
            abusive behavior.
          </p>
          <ul className="space-y-2">
            {[
              'Accounts with no paid subscription may receive a warning email 14 days before removal',
              'If you do not subscribe within 3 months of signup, your account and all personal data may be permanently deleted',
              'Deleted data includes profile, lab history, interview transcripts, and payment metadata linked to your account',
              'You may create a new account at any time after deletion',
              'You can permanently delete your account anytime in Profile → Delete account',
              'You can opt out of marketing emails via the unsubscribe link in emails or Profile → Notifications',
              'Users with active subscriptions are never removed under this policy',
            ].map((item, i) => (
              <li key={i} className="flex items-start gap-3 text-surface-300">
                <span className="w-1.5 h-1.5 rounded-full bg-red-400 mt-2 shrink-0" />
                <span className="leading-relaxed">{item}</span>
              </li>
            ))}
          </ul>
        </>
      ),
    },
  ]

  return (
    <PublicLayout>
      <div className="relative overflow-hidden">
        {/* Decorative background */}
        <div className="absolute inset-0 pointer-events-none">
          <div className="absolute top-20 left-1/4 w-96 h-96 bg-accent-cyan/5 rounded-full blur-3xl" />
          <div className="absolute bottom-40 right-1/4 w-72 h-72 bg-accent-purple/5 rounded-full blur-3xl" />
        </div>

        <div className="max-w-4xl mx-auto px-4 py-16 relative">
          {/* Hero */}
          <div className="text-center mb-16 animate-fade-in">
            <div className="w-20 h-20 mx-auto mb-6 rounded-2xl bg-gradient-to-br from-cyan-500/20 to-blue-500/20 border border-cyan-500/20 flex items-center justify-center">
              <ScrollText size={36} className="text-cyan-400" />
            </div>
            <h1 className="text-5xl font-extrabold mb-4 bg-gradient-to-r from-white via-cyan-300 to-cyan-500 bg-clip-text text-transparent">
              Terms of Service
            </h1>
            <p className="text-surface-400 text-lg">Last updated: June 5, 2026</p>
            <div className="w-20 h-1 bg-gradient-to-r from-accent-cyan to-accent-purple rounded-full mx-auto mt-6" />
          </div>

          {/* Sections */}
          <div className="space-y-6">
            {sections.map((section, i) => {
              const Icon = section.icon
              return (
                <section
                  key={i}
                  className="glass-card p-8 hover:border-accent-cyan/20 transition-all duration-300 animate-fade-in"
                  style={{ animationDelay: `${i * 0.1}s` }}
                >
                  <div className="flex items-center gap-4 mb-5">
                    <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${section.color} flex items-center justify-center shadow-lg`}>
                      <Icon size={20} className="text-white" />
                    </div>
                    <h2 className="text-xl font-bold text-white">{section.title}</h2>
                  </div>
                  {section.content}
                </section>
              )
            })}

            {/* Contact */}
            <section className="glass-card p-8 border-accent-cyan/20 bg-gradient-to-br from-accent-cyan/5 to-transparent animate-fade-in">
              <h2 className="text-xl font-bold text-white mb-4">7. Contact</h2>
              <p className="text-surface-300 leading-relaxed">
                Questions about these terms? Contact us at{' '}
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
