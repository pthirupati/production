import PublicLayout from '../components/layout/PublicLayout'
import MarketingPageShell from '../components/MarketingPageShell'
import { FixitPanel } from '../components/design'
import { Shield, Terminal, Users, AlertTriangle, ExternalLink, FileText } from 'lucide-react'
import { usePageTitle } from '../hooks/usePageTitle'
import { PRIMARY_EMAIL, SUPPORT_EMAIL } from '../constants/contact'

/**
 * Acceptable Use Policy (audit Z4-12 leftover).
 * Written from measured product rules — Terms §2, lab capacity caps, community
 * throttles, and sandbox isolation — not a generic template. DPA / platform SLA
 * remain separate counsel-owned documents if enterprise needs them.
 */
export default function AcceptableUse() {
  usePageTitle(
    'Acceptable Use',
    'What you may and may not do on FixitLab labs, interviews, and community features.',
  )

  const sections = [
    {
      icon: Shield,
      title: 'Intended use',
      color: 'from-emerald-500 to-green-600',
      items: [
        'FixitLab is for learning and practising technology skills in isolated lab and interview environments.',
        'Use the platform only for its intended educational purpose.',
        'Comply with all applicable laws and regulations where you use the service.',
      ],
    },
    {
      icon: Terminal,
      title: 'Labs and sandboxes',
      color: 'from-cyan-500 to-blue-600',
      items: [
        'Lab environments are provided for the scenario you started. Do not attempt to reach other users’ labs, accounts, or data.',
        'Do not attempt to escape the sandbox, attack the host platform, or circumvent capacity, authentication, or access controls.',
        'Do not use labs for cryptocurrency mining, bulk outbound spam, or any activity whose purpose is not completing the learning scenario.',
        'Concurrent labs are limited per user and platform-wide to protect shared capacity. Hitting a limit is not a licence to open more sessions through alternate accounts.',
      ],
    },
    {
      icon: Users,
      title: 'Accounts, interviews, and community',
      color: 'from-violet-500 to-purple-600',
      items: [
        'Do not share your account credentials. One person per account.',
        'Do not create accounts solely to reset free trials, free interview campaigns, or other usage caps.',
        'Interview sessions require honest participation — do not attempt to defeat proctoring or scoring by automated answer injection or session hijacking.',
        'Community posts and replies must not harass, threaten, or spam others. Abuse reports are reviewed; repeated violations may lead to suspension.',
      ],
    },
    {
      icon: AlertTriangle,
      title: 'Enforcement',
      color: 'from-amber-500 to-orange-600',
      items: [
        'We may suspend or terminate accounts that violate this policy or the Terms of Service.',
        'We may refuse or throttle actions that look like automated abuse (rate limits apply to community writes and similar endpoints).',
        'Serious security abuse may be reported to relevant authorities where required by law.',
      ],
    },
  ]

  return (
    <PublicLayout>
      <MarketingPageShell
        narrow
        eyebrow="Legal"
        title={
          <span className="bg-gradient-to-r from-white via-emerald-200 to-green-400 bg-clip-text text-transparent">
            Acceptable Use
          </span>
        }
        subtitle="Last updated: August 10, 2026"
      >
        <div className="space-y-6">
          <FixitPanel padding="p-8" className="animate-fade-in">
            <p className="text-surface-300 leading-relaxed">
              This Acceptable Use Policy supplements the{' '}
              <a href="/terms" className="text-accent-cyan hover:underline">Terms of Service</a>
              . If something is forbidden here, it is also a Terms violation. It describes
              how the product is actually guarded today — capacity caps, sandboxes, and
              community throttles — not aspirational rules we do not enforce.
            </p>
          </FixitPanel>

          {sections.map((section) => {
            const Icon = section.icon
            return (
              <FixitPanel
                key={section.title}
                padding="p-8"
                className="hover:border-accent-cyan/20 transition-all duration-300 animate-fade-in"
              >
                <div className="flex items-center gap-4 mb-5">
                  <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${section.color} flex items-center justify-center shadow-lg`}>
                    <Icon size={20} className="text-white" />
                  </div>
                  <h2 className="text-xl font-bold text-white">{section.title}</h2>
                </div>
                <ul className="space-y-2">
                  {section.items.map((item) => (
                    <li key={item} className="flex items-start gap-3 text-surface-300">
                      <span className="w-1.5 h-1.5 rounded-full bg-accent-green mt-2 shrink-0" />
                      <span className="leading-relaxed">{item}</span>
                    </li>
                  ))}
                </ul>
              </FixitPanel>
            )
          })}

          <FixitPanel hero padding="p-8" className="border-accent-green/20 animate-fade-in">
            <div className="flex items-center gap-4 mb-5">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-500 to-green-600 flex items-center justify-center shadow-lg">
                <FileText size={20} className="text-white" />
              </div>
              <h2 className="text-xl font-bold text-white">Contact</h2>
            </div>
            <p className="text-surface-300 leading-relaxed">
              Questions about this policy:{' '}
              <a href={`mailto:${PRIMARY_EMAIL}`} className="inline-flex items-center gap-1 text-accent-cyan hover:underline font-medium">
                {PRIMARY_EMAIL} <ExternalLink size={12} />
              </a>
              . Report abuse or support issues:{' '}
              <a href={`mailto:${SUPPORT_EMAIL}`} className="inline-flex items-center gap-1 text-accent-cyan hover:underline font-medium">
                {SUPPORT_EMAIL} <ExternalLink size={12} />
              </a>
              . Related:{' '}
              <a href="/privacy" className="text-accent-cyan hover:underline">Privacy</a>
              {' · '}
              <a href="/refunds" className="text-accent-cyan hover:underline">Refunds</a>
              .
            </p>
          </FixitPanel>
        </div>
      </MarketingPageShell>
    </PublicLayout>
  )
}
