import { useState, useMemo } from 'react'
import PublicLayout from '../components/layout/PublicLayout'
import MarketingPageShell from '../components/MarketingPageShell'
import { FixitPanel } from '../components/design'
import { useRevealOnScroll } from '../hooks/useRevealOnScroll'
import {
  HelpCircle, ChevronDown, Search, X,
  Rocket, CreditCard, Terminal, Brain, Award, UserCircle
} from 'lucide-react'

const CATEGORY_META = {
  'Getting Started':         { icon: Rocket,     color: 'text-accent-cyan',   bg: 'bg-accent-cyan/10',   border: 'border-accent-cyan/20'   },
  'Subscriptions & Pricing': { icon: CreditCard, color: 'text-accent-green',  bg: 'bg-accent-green/10',  border: 'border-accent-green/20'  },
  'Labs & Scenarios':        { icon: Terminal,   color: 'text-accent-purple', bg: 'bg-accent-purple/10', border: 'border-accent-purple/20' },
  'AI Interview Studio':     { icon: Brain,      color: 'text-accent-blue',   bg: 'bg-accent-blue/10',   border: 'border-accent-blue/20'   },
  'Certificates':            { icon: Award,      color: 'text-accent-amber',  bg: 'bg-accent-amber/10',  border: 'border-accent-amber/20'  },
  'Account & Support':       { icon: UserCircle, color: 'text-accent-pink',   bg: 'bg-accent-pink/10',   border: 'border-accent-pink/20'   },
}

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
        a: "Sign up for a free account, browse available scenarios, and start a lab. You'll get a live terminal connected to a broken server. Diagnose the issue and fix it within the time limit.",
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
        a: 'Subscriptions are per-technology. You only pay for the technologies you want to learn. Free users can access sample labs to try the platform.',
      },
      {
        // The refund path is manual by design (an admin issues it through the
        // gateway), so the copy says so rather than implying self-serve. It also
        // now states that access ends on a full refund, which is what the backend
        // actually does since RazorpayRefundView started revoking entitlement —
        // previously a refunded user silently kept a year of paid access.
        q: 'Can I get a refund?',
        a: 'Yes — within 7 days of purchase. Email fixitlab.payment@gmail.com with your subscription ID and we will process it manually, usually within two business days. Refunds are returned to the original payment method by the payment gateway. Note that a full refund ends access to that technology; a partial refund does not.',
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
        q: "What happens if I can't solve a scenario?",
        a: 'You can use hints (limited per scenario) to get guidance. After the timer expires, you can view the full solution explanation.',
      },
      {
        q: 'Can I replay a completed scenario?',
        a: 'Yes! You can restart any scenario to improve your score or practice. Your best score is tracked on the leaderboard.',
      },
      {
        q: 'How do Jira bots work in AI labs?',
        a: 'Each lab can have a Jira ticket. Comment on the ticket for customer impact/timeline (customer bot). Mention @backup team, @database team, @application team for patching, @storage team for disks, or @network team for NIC/IP — team bots reply after ~30 seconds and update the server. Use the terminal after confirmations.',
      },
      {
        q: 'What is the FixitLab Assistant (Help bot)?',
        a: 'A floating Help button on every page for platform questions: how to launch labs, subscribe, interviews, certificates, and who to email. It does not answer Jira ticket or @team questions — use the Jira panel inside your lab for those. Disable it anytime from Profile → FixitLab Assistant.',
      },
    ],
  },
  {
    category: 'AI Interview Studio',
    items: [
      {
        q: 'What is AI Interview Studio?',
        a: 'A multi-round AI interview product on FixitLab. Upload your resume, pick 3–5 rounds (technical, manager, HR, etc.), and practice with voice Q&A in your browser.',
      },
      {
        q: 'Do I need camera and microphone?',
        a: 'Yes. Mic and camera must stay on during each round. You get a 5-minute grace period to re-enable them; after that the session may end automatically.',
      },
      {
        q: 'How is Interview Studio priced?',
        a: 'Separate monthly plans: Free mini (1 cycle), Pro (₹999), Premium (₹2,499). This is independent of per-technology lab subscriptions. See Pricing or /mock-interviews.',
      },
      {
        q: 'How do interview certificates work?',
        a: 'Pass all rounds in a campaign to earn a FIXIT-INT certificate. Verify any certificate at /verify-certificate — IDs start with FIXIT-INT.',
      },
      {
        q: 'Can an admin join my interview?',
        a: 'Only if you approve. Admins can request to observe a live session; you see a prompt in the interview room to approve or decline.',
      },
    ],
  },
  {
    category: 'Certificates',
    items: [
      {
        q: 'How do I earn a technology certificate?',
        a: "Complete ALL scenarios within a technology and you'll be able to download a certificate. You must be a paid subscriber of that technology.",
      },
      {
        q: 'How do I earn an interview certificate?',
        a: 'Complete all rounds in an Interview Studio campaign with passing scores. Premium plans include certificate issuance.',
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
        a: 'Yes, you can request account deletion by contacting our support team. All your data — including lab history, interview transcripts, and uploaded resumes — will be permanently removed within 30 days.',
      },
    ],
  },
]

function FAQItem({ question, answer }) {
  const [open, setOpen] = useState(false)
  return (
    <FixitPanel padding="p-0" className={`overflow-hidden transition-all duration-200 ${open ? 'border-accent-cyan/30' : ''}`}>
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between p-5 text-left gap-4 hover:bg-surface-800/30 transition-colors group"
      >
        <span className="font-medium text-white group-hover:text-accent-cyan transition-colors leading-snug">{question}</span>
        <span className={`shrink-0 w-7 h-7 rounded-lg flex items-center justify-center transition-all duration-200 ${open ? 'bg-accent-cyan/20 text-accent-cyan rotate-180' : 'bg-surface-700/60 text-surface-400'}`}>
          <ChevronDown size={16} />
        </span>
      </button>
      <div className={`overflow-hidden transition-all duration-300 ${open ? 'max-h-[600px] opacity-100' : 'max-h-0 opacity-0'}`}>
        <div className="px-5 pb-5 pt-0 text-sm text-surface-300 border-t border-surface-700/40 leading-relaxed">
          <div className="pt-4">{answer}</div>
        </div>
      </div>
    </FixitPanel>
  )
}

export default function FAQ() {
  const [search, setSearch] = useState('')

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    if (!q) return FAQ_ITEMS
    return FAQ_ITEMS.map(cat => ({
      ...cat,
      items: cat.items.filter(
        item => item.q.toLowerCase().includes(q) || item.a.toLowerCase().includes(q)
      ),
    })).filter(cat => cat.items.length > 0)
  }, [search])

  const totalResults = filtered.reduce((n, c) => n + c.items.length, 0)

  // FAQ category/question cards use `.reveal` (opacity:0 until `.visible`).
  // Re-scan when the filtered results change so search hits are revealed too.
  useRevealOnScroll([filtered])

  return (
    <PublicLayout>
      <MarketingPageShell
        narrow
        eyebrow="Help center"
        title={
          <>
            Frequently Asked{' '}
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-accent-cyan to-accent-blue">
              Questions
            </span>
          </>
        }
        subtitle="Find answers to common questions about FixitLab"
      >
        {/* Search */}
        <div className="relative max-w-xl mx-auto mb-12 -mt-4">
          <Search size={18} className="absolute left-4 top-1/2 -translate-y-1/2 text-surface-400 pointer-events-none" />
          <input
            type="text"
            placeholder="Search questions..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="input-field pl-11 pr-11 py-3 w-full text-base"
          />
          {search && (
            <button
              onClick={() => setSearch('')}
              className="absolute right-3 top-1/2 -translate-y-1/2 w-7 h-7 flex items-center justify-center rounded-md text-surface-400 hover:text-white hover:bg-surface-700 transition-colors"
            >
              <X size={14} />
            </button>
          )}
          {search && (
            <p className="text-sm text-surface-500 mt-3 text-center">
              {totalResults === 0
                ? 'No results found'
                : `${totalResults} result${totalResults !== 1 ? 's' : ''} for "${search}"`}
            </p>
          )}
        </div>

        {filtered.length === 0 ? (
          <FixitPanel padding="p-12" className="text-center">
            <HelpCircle size={40} className="text-surface-500 mx-auto mb-3" />
            <p className="text-surface-400">No questions match your search. Try different keywords.</p>
            <button onClick={() => setSearch('')} className="btn-secondary mt-4 text-sm">Clear search</button>
          </FixitPanel>
        ) : (
          <div className="space-y-10 animate-slide-up">
            {filtered.map((cat, catIdx) => {
              const meta = CATEGORY_META[cat.category] || {
                icon: HelpCircle,
                color: 'text-accent-cyan',
                bg: 'bg-accent-cyan/10',
                border: 'border-accent-cyan/20',
              }
              const Icon = meta.icon
              const catRevealDelays = ['reveal-delay-1','reveal-delay-2','reveal-delay-3','reveal-delay-4','reveal-delay-5','reveal-delay-6']
              return (
                <div key={cat.category} className={`reveal ${catRevealDelays[catIdx % catRevealDelays.length]}`}>
                  <div className={`inline-flex items-center gap-2.5 px-4 py-2 rounded-xl ${meta.bg} border ${meta.border} mb-4`}>
                    <Icon size={16} className={meta.color} />
                    <h2 className={`text-sm font-bold ${meta.color}`}>{cat.category}</h2>
                    <span className={`ml-1 px-1.5 py-0.5 text-xs rounded-md bg-surface-900/60 ${meta.color} font-medium`}>
                      {cat.items.length}
                    </span>
                  </div>
                  <div className="space-y-2">
                    {cat.items.map((item, itemIdx) => {
                      const itemDelays = ['reveal-delay-1','reveal-delay-2','reveal-delay-3','reveal-delay-4']
                      return (
                        <div key={item.q} className={`reveal ${itemDelays[itemIdx % itemDelays.length]}`}>
                          <FAQItem question={item.q} answer={item.a} />
                        </div>
                      )
                    })}
                  </div>
                </div>
              )
            })}
          </div>
        )}

        <FixitPanel hero padding="p-8" className="mt-14 text-center relative overflow-hidden">
          <div className="absolute inset-0 bg-gradient-to-br from-accent-cyan/5 via-transparent to-accent-purple/5 pointer-events-none" />
          <div className="relative">
            <HelpCircle size={28} className="text-accent-cyan mx-auto mb-3" />
            <h3 className="text-xl font-bold text-white mb-2">Still have questions?</h3>
            <p className="text-surface-400 mb-5 text-sm">Our support team is here to help. Typically responds within 24 hours.</p>
            <a href="mailto:fixitlab.techsupport@gmail.com" className="btn-primary inline-flex items-center gap-2">
              Contact Support
            </a>
          </div>
        </FixitPanel>
      </MarketingPageShell>
    </PublicLayout>
  )
}
