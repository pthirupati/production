import { useState } from 'react'
import PublicLayout from '../components/layout/PublicLayout'
import { HelpCircle, ChevronDown, ChevronUp } from 'lucide-react'

const FAQ_ITEMS = [
  {
    category: 'Getting Started',
    items: [
      {
        q: 'What is FixitLab?',
        a: 'FixitLab is a hands-on learning platform where you practice real-world technology skills in live terminal environments. From Linux and networking to Docker, databases, cloud, and security — connect to real environments, solve challenges, and learn by doing.',

      },
      {
        q: 'How do I get started?',
        a: 'Sign up for a free account, browse available scenarios, and start a lab. You\'ll get a live terminal connected to a broken server. Diagnose the issue and fix it within the time limit.',
      },
      {
        q: 'What technologies are available?',
        a: 'We currently offer scenarios for Linux, Networking, and more. New technologies are added regularly. Each technology has multiple scenarios ranging from easy to hard difficulty.',
      },
    ],
  },
  {
    category: 'Subscriptions & Pricing',
    items: [
      {
        q: 'How does pricing work?',
        a: 'Subscriptions are per-technology. You only pay for the technologies you want to learn. Free users can access demo scenarios to try the platform.',
      },
      {
        q: 'Can I get a refund?',
        a: 'Yes, we offer refunds within 7 days of purchase. Contact us at fixitlab.payment@gmail.com with your subscription ID.',
      },
      {
        q: 'Do you offer student discounts?',
        a: 'Yes! Students with a valid .edu email can get discounted access. Contact fixitlab.techsupport@gmail.com with your student ID for verification.',
      },
      {
        q: 'What happens when my subscription expires?',
        a: 'You lose access to the paid scenarios for that technology but retain your progress and certificates. You can resubscribe at any time.',
      },
    ],
  },
  {
    category: 'Labs & Scenarios',
    items: [
      {
        q: 'How long does each lab last?',
        a: 'Most labs have a time limit of 15-30 minutes. The time limit varies by scenario difficulty. Your progress is saved even if the timer expires.',
      },
      {
        q: 'What happens if I can\'t solve a scenario?',
        a: 'You can use hints (limited per scenario) to get guidance. After the timer expires, you can view the full solution explanation.',
      },
      {
        q: 'Can I replay a completed scenario?',
        a: 'Yes! You can restart any scenario to improve your score or practice. Your best score is tracked on the leaderboard.',
      },
    ],
  },
  {
    category: 'Certificates',
    items: [
      {
        q: 'How do I earn a certificate?',
        a: 'Complete ALL scenarios within a technology and you\'ll be able to download a certificate. You must be a paid subscriber of that technology.',
      },
      {
        q: 'Are certificates shareable?',
        a: 'Yes, each certificate has a unique ID that can be verified. You can share it on LinkedIn or your resume.',
      },
    ],
  },
  {
    category: 'Account & Support',
    items: [
      {
        q: 'How do I contact support?',
        a: 'Email us at fixitlab.techsupport@gmail.com or use the Contact page. We typically respond within 24 hours.',
      },
      {
        q: 'Can I delete my account?',
        a: 'Yes, you can request account deletion by contacting our support team. All your data will be permanently removed within 30 days.',
      },
    ],
  },
]

function FAQItem({ question, answer }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="glass-card overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between p-4 text-left hover:bg-surface-800/50 transition-colors"
      >
        <span className="font-medium pr-4">{question}</span>
        {open ? <ChevronUp size={18} className="text-surface-400 shrink-0" /> : <ChevronDown size={18} className="text-surface-400 shrink-0" />}
      </button>
      {open && (
        <div className="px-4 pb-4 text-sm text-surface-300 border-t border-surface-700/50 pt-3">
          {answer}
        </div>
      )}
    </div>
  )
}

export default function FAQ() {
  return (
    <PublicLayout>
      <div className="max-w-4xl mx-auto px-4 py-16">
        <div className="text-center mb-12">
          <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-gradient-to-br from-cyan-500/20 to-blue-500/20 flex items-center justify-center">
            <HelpCircle size={32} className="text-cyan-400" />
          </div>
          <h1 className="text-4xl font-bold mb-2">Frequently Asked Questions</h1>
          <p className="text-surface-400">Find answers to common questions about FixitLab</p>
        </div>

        <div className="space-y-8">
          {FAQ_ITEMS.map((category) => (
            <div key={category.category}>
              <h2 className="text-lg font-bold mb-3 text-cyan-400">{category.category}</h2>
              <div className="space-y-2">
                {category.items.map((item) => (
                  <FAQItem key={item.q} question={item.q} answer={item.a} />
                ))}
              </div>
            </div>
          ))}
        </div>

        <div className="mt-12 text-center glass-card p-8">
          <h3 className="text-xl font-bold mb-2">Still have questions?</h3>
          <p className="text-surface-400 mb-4">Our support team is here to help.</p>
          <a href="mailto:fixitlab.techsupport@gmail.com" className="btn-primary inline-flex items-center gap-2">
            Contact Support
          </a>
        </div>
      </div>
    </PublicLayout>
  )
}
