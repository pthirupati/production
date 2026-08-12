import PublicLayout from '../components/layout/PublicLayout'
import MarketingPageShell from '../components/MarketingPageShell'
import { FixitPanel } from '../components/design'
import { CreditCard, Ban, RefreshCcw, ExternalLink, FileText } from 'lucide-react'
import { usePageTitle } from '../hooks/usePageTitle'
import { PAYMENT_EMAIL, SUPPORT_EMAIL } from '../constants/contact'

/**
 * Standalone refund & cancellation policy (audit Z4-12 leftover).
 * Written from measured product behaviour — FAQ, Terms, RazorpayRefundView
 * entitlement revoke, and Dashboard cancel-at-period-end (Z1-11) — not a
 * template. Indian payment gateways expect a linkable page; FAQ alone is not one.
 */
export default function RefundCancellation() {
  usePageTitle(
    'Refunds & Cancellation',
    'How FixitLab handles refunds within 7 days and subscription cancellation at period end.',
  )

  const sections = [
    {
      icon: RefreshCcw,
      title: 'Refunds',
      color: 'from-amber-500 to-orange-600',
      items: [
        'You may request a refund within 7 days of purchase.',
        `Email ${PAYMENT_EMAIL} with your subscription ID (or payment reference). Requests are processed manually — usually within two business days.`,
        'Approved refunds are returned to the original payment method by Razorpay (INR) or Stripe (USD). FixitLab never stores your card number, CVV, or UPI PIN.',
        'A full refund ends access to that technology (or Interview Studio entitlement). A partial refund does not revoke access.',
        'Complimentary or admin-granted free access is not a paid purchase and is not refundable.',
      ],
    },
    {
      icon: Ban,
      title: 'Cancellation',
      color: 'from-rose-500 to-red-600',
      items: [
        'You can cancel a technology subscription from your Dashboard while it is active.',
        'Cancellation takes effect at the end of the paid term — you keep full access until that date, and the subscription simply does not renew.',
        'Progress, lab history, and certificates are kept after cancellation or expiry.',
        'Cancelling is not the same as a refund. If you want money back within the 7-day window, use the refund path above.',
      ],
    },
    {
      icon: CreditCard,
      title: 'Payments',
      color: 'from-cyan-500 to-blue-600',
      items: [
        'Technology subscriptions are charged per technology for 1-year access.',
        'Interview Studio plans (Pro/Premium) are billed separately with their own attempt limits and validity.',
        'Bank OTP, 3D Secure, and UPI authentication are handled entirely by the payment gateway.',
        `Billing questions that are not refunds: ${SUPPORT_EMAIL}.`,
      ],
    },
  ]

  return (
    <PublicLayout>
      <MarketingPageShell
        narrow
        eyebrow="Legal"
        title={
          <span className="bg-gradient-to-r from-white via-amber-200 to-orange-400 bg-clip-text text-transparent">
            Refunds &amp; Cancellation
          </span>
        }
        subtitle="Last updated: August 10, 2026"
      >
        <div className="space-y-6">
          <FixitPanel padding="p-8" className="animate-fade-in">
            <p className="text-surface-300 leading-relaxed">
              This page is the linkable refund and cancellation policy for FixitLab
              purchases. It matches how the product actually behaves — not a generic
              template. The short FAQ answer on refunds points here for the full detail.
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
                      <span className="w-1.5 h-1.5 rounded-full bg-accent-amber mt-2 shrink-0" />
                      <span className="leading-relaxed">{item}</span>
                    </li>
                  ))}
                </ul>
              </FixitPanel>
            )
          })}

          <FixitPanel hero padding="p-8" className="border-accent-amber/20 animate-fade-in">
            <div className="flex items-center gap-4 mb-5">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-amber-500 to-orange-600 flex items-center justify-center shadow-lg">
                <FileText size={20} className="text-white" />
              </div>
              <h2 className="text-xl font-bold text-white">Contact</h2>
            </div>
            <p className="text-surface-300 leading-relaxed">
              Refund requests:{' '}
              <a href={`mailto:${PAYMENT_EMAIL}`} className="inline-flex items-center gap-1 text-accent-cyan hover:underline font-medium">
                {PAYMENT_EMAIL} <ExternalLink size={12} />
              </a>
              . Other billing questions:{' '}
              <a href={`mailto:${SUPPORT_EMAIL}`} className="inline-flex items-center gap-1 text-accent-cyan hover:underline font-medium">
                {SUPPORT_EMAIL} <ExternalLink size={12} />
              </a>
              .
            </p>
          </FixitPanel>
        </div>
      </MarketingPageShell>
    </PublicLayout>
  )
}
