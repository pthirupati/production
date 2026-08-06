import PublicLayout from '../components/layout/PublicLayout'
import MarketingPageShell from '../components/MarketingPageShell'
import { FixitPanel } from '../components/design'
import { Shield, Lock, Eye, Database, UserCheck, FileText, ExternalLink, Cookie } from 'lucide-react'
import { usePageTitle } from '../hooks/usePageTitle'
import { PRIVACY_EMAIL } from '../constants/contact'

export default function Privacy() {
  usePageTitle('Privacy Policy', 'What data FixitLab collects, who processes it, how long we keep it, and how to exercise your rights.')
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
        'Interview transcripts, scores, and session metadata from AI interviews',
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
        'To run AI interviews using our own rule-based engine (no third-party LLM APIs)',
        'To process voice answers via your browser’s built-in Speech API. Note: in Chrome and Edge this sends your audio to Google’s speech service for transcription — it is not processed on your device. Firefox and Safari differ. We receive only the resulting text, never the audio, and we do not use any paid speech service.',
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
      text: 'We implement industry-standard security measures including encrypted data transmission (TLS), hashed passwords, secure authentication tokens, and regular security audits to protect your data. Lab sessions are isolated in containers that are destroyed after use.',
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
    {
      // Audit Z4-8. Written from a measurement of what the code actually sets,
      // not from a template. Naming a cookie we do not use would be as wrong as
      // omitting one we do.
      icon: Cookie,
      title: 'Cookies and Local Storage',
      color: 'from-rose-500 to-pink-600',
      text: 'We use only what the service needs to work. There are no advertising cookies, no analytics cookies, and no third-party trackers on FixitLab — so there is nothing here to opt out of, and that is why you are not asked to dismiss a consent banner. If that ever changes we will ask for your consent first, before the cookie is set.',
      items: [
        'access_token and refresh_token — httpOnly cookies that keep you signed in. Without these you cannot stay logged in.',
        'csrftoken — Django’s cross-site request forgery protection. Required to submit any form securely.',
        'Local storage: your theme choice, your signed-in session state, whether you dismissed the onboarding tips, and small guards that stop the app reloading in a loop after a deploy.',
        'Session storage: short-lived UI acknowledgements, such as confirming you understand a lab needs a full-size screen.',
        'None of the above is shared with anyone, and clearing them only signs you out and resets your preferences.',
      ],
    },
  ]

  return (
    <PublicLayout>
      <MarketingPageShell
        narrow
        eyebrow="Legal"
        title={
          <span className="bg-gradient-to-r from-white via-green-300 to-cyan-400 bg-clip-text text-transparent">
            Privacy Policy
          </span>
        }
        subtitle="Last updated: August 8, 2026"
      >
        <div className="space-y-6">
          {sections.map((section, i) => {
            const Icon = section.icon
            return (
              <FixitPanel
                key={i}
                padding="p-8"
                className="hover:border-accent-green/20 transition-all duration-300 animate-fade-in"
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
                  <ul className={`space-y-2${section.text ? ' mt-4' : ''}`}>
                    {section.items.map((item, j) => (
                      <li key={j} className="flex items-start gap-3 text-surface-300">
                        <span className="w-1.5 h-1.5 rounded-full bg-accent-green mt-2 shrink-0" />
                        <span className="leading-relaxed">{item}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </FixitPanel>
            )
          })}

          <FixitPanel padding="p-8" className="border-indigo-500/20 animate-fade-in">
            <h2 className="text-xl font-bold text-white mb-4">AI Interview Studio</h2>
            <ul className="space-y-2 text-surface-300 text-sm">
              <li>AI interviews require camera and microphone; you must consent before each session.</li>
              <li>We store text transcripts and scores. Video is not recorded on our servers unless explicitly stated.</li>
              <li>
                Voice uses your browser&apos;s built-in speech APIs. We pay no third-party
                TTS/STT provider, but &ldquo;free&rdquo; is not the same as &ldquo;private&rdquo;: in Chrome and
                Edge, speech recognition sends your audio to Google for transcription.
                FixitLab receives only the text. If you would rather not send audio to
                Google, type your answers instead — every question accepts typed input.
              </li>
              <li>Admins may request to observe a live session; you must approve before they can view the transcript.</li>
              <li>Interview data is retained while your account is active and deleted with account deletion requests.</li>
            </ul>
          </FixitPanel>

          <FixitPanel hero padding="p-8" className="border-accent-green/20 animate-fade-in">
            <h2 className="text-xl font-bold text-white mb-4">Exercising your rights</h2>
            <p className="text-surface-300 text-sm mb-3">
              Most of these you can do yourself, immediately, without asking us:
            </p>
            <ul className="space-y-2 text-surface-300 text-sm">
              <li><strong className="text-white">Get a copy of your data</strong> — Profile → Download my data. Returns everything we hold: profile, labs, interviews, certificates, billing and preferences.</li>
              <li><strong className="text-white">Delete your resume</strong> — Interview Studio → profile. Removes the file and the parsed text.</li>
              <li><strong className="text-white">Delete an interview</strong> — from your interview history. Removes the transcript and report.</li>
              <li><strong className="text-white">Withdraw marketing consent</strong> — Profile → Notifications, or the unsubscribe link in any marketing email.</li>
              <li><strong className="text-white">Delete your account</strong> — Profile → Delete account. Removes your data, including uploaded files.</li>
            </ul>
            <p className="text-surface-300 text-sm mt-4">
              For anything else — correction, restriction, or a complaint about how we
              handled your data — email the grievance contact below. We acknowledge
              within <strong className="text-white">3 working days</strong> and respond
              substantively within <strong className="text-white">30 days</strong>. If
              you are not satisfied with our response, you may complain to the Data
              Protection Board of India.
            </p>
          </FixitPanel>

          <FixitPanel hero padding="p-8" className="border-accent-green/20 animate-fade-in">
            <h2 className="text-xl font-bold text-white mb-4">How interview scoring works</h2>
            <ul className="space-y-2 text-surface-300 text-sm">
              <li>
                Your interview is scored <strong className="text-white">automatically</strong>, by a
                rule-based engine we wrote — not by a human reviewer and not by a
                third-party AI service. It compares your answers against expected
                keywords and concepts for each question, and weighs answer depth,
                relevance and consistency.
              </li>
              <li>
                A pass/fail recommendation is produced by comparing your overall score
                against a fixed threshold for that round. Your report shows the score,
                the per-topic breakdown, and the reasoning behind it.
              </li>
              <li>
                <strong className="text-white">It is practice, not a hiring decision.</strong> FixitLab
                does not share your results with employers, and no employment outcome
                follows from them.
              </li>
              <li>
                If you believe a score is wrong, email us and a human will review the
                transcript and correct it. You can also retake a round, and you can
                delete an interview and its transcript at any time.
              </li>
            </ul>
          </FixitPanel>

          <FixitPanel hero padding="p-8" className="border-accent-green/20 animate-fade-in">
            <h2 className="text-xl font-bold text-white mb-4">Who else processes your data</h2>
            <p className="text-surface-300 text-sm mb-3">
              We use the following service providers. We share only what each one needs
              to do its job — never your lab work or interview transcripts for
              advertising, and we do not sell personal data.
            </p>
            <ul className="space-y-2 text-surface-300 text-sm">
              <li><strong className="text-white">DigitalOcean</strong> — hosting and databases for the platform. Data is stored in their Bangalore (India) region.</li>
              <li><strong className="text-white">Razorpay</strong> and <strong className="text-white">Stripe</strong> — payment processing. They receive your payment details directly; we never store card numbers.</li>
              <li><strong className="text-white">Google</strong> — optional &ldquo;Sign in with Google&rdquo; (we receive your email and name), and, if you use voice answers in Chrome or Edge, your browser sends the audio to Google&apos;s speech service for transcription.</li>
              <li><strong className="text-white">Sentry</strong> — error monitoring, when enabled. Receives crash diagnostics which may include your user ID.</li>
              <li><strong className="text-white">Atlassian Jira</strong> — only if your organisation connects it for ticket-based labs. Off by default; labs use a built-in simulated ticket system.</li>
            </ul>
            <p className="text-surface-400 text-xs mt-3">
              Some of these providers operate outside India and your data may be
              processed there.
            </p>
          </FixitPanel>

          <FixitPanel hero padding="p-8" className="border-accent-green/20 animate-fade-in">
            <div className="flex items-center gap-4 mb-5">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center shadow-lg">
                <FileText size={20} className="text-white" />
              </div>
              <h2 className="text-xl font-bold text-white">Contact</h2>
            </div>
            <p className="text-surface-300 leading-relaxed">
              Our grievance contact for privacy questions, data requests and
              complaints is{' '}
              <a href={`mailto:${PRIVACY_EMAIL}`} className="inline-flex items-center gap-1 text-accent-cyan hover:underline font-medium">
                {PRIVACY_EMAIL} <ExternalLink size={12} />
              </a>
            </p>
          </FixitPanel>
        </div>
      </MarketingPageShell>
    </PublicLayout>
  )
}
