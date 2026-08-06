import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { X, ArrowRight, ArrowLeft, Terminal, Target, Trophy, Layers, Sparkles } from 'lucide-react'
import { currentUserScopedKey, migrateUnscopedKey } from '../utils/userScopedStorage'

const TOUR_STEPS = [
  {
    icon: Sparkles,
    title: 'Welcome to FixitLab!',
    description: 'Master DevOps and Linux by fixing real, broken environments. Let us show you around.',
    color: 'accent-cyan',
  },
  {
    icon: Layers,
    title: 'Browse Technologies',
    description: 'Start by exploring technologies like Linux, Docker, Kubernetes, and Networking. Subscribe to unlock all scenarios.',
    color: 'accent-purple',
    action: '/technologies',
  },
  {
    icon: Target,
    title: 'Choose a Scenario',
    description: 'Each scenario is a real broken environment. Fix, Do, or Hack — pick your challenge type and difficulty level.',
    color: 'accent-green',
    action: '/scenarios',
  },
  {
    icon: Terminal,
    title: 'Launch a Lab',
    description: 'Click "Start Challenge" to get a real terminal. Run actual Linux commands to investigate and fix the issue.',
    color: 'accent-amber',
  },
  {
    icon: Trophy,
    title: 'Track Progress',
    description: 'Earn achievements, climb the leaderboard, and build your skills profile. Your activity heatmap shows your consistency.',
    color: 'accent-cyan',
    action: '/achievements',
  },
]

// Scoped per user: an unscoped key meant a second account on a shared browser
// was treated as already onboarded and never saw the tour.
const TOUR_KEY_BASE = 'fixitlab_tour_completed'

export default function OnboardingTour() {
  const [step, setStep] = useState(0)
  const [show, setShow] = useState(false)
  const navigate = useNavigate()

  useEffect(() => {
    const completed = localStorage.getItem(migrateUnscopedKey(TOUR_KEY_BASE))
    if (!completed) {
      // Show tour after a brief delay
      const timer = setTimeout(() => setShow(true), 1500)
      return () => clearTimeout(timer)
    }
  }, [])

  const handleNext = () => {
    if (step < TOUR_STEPS.length - 1) {
      setStep(step + 1)
    } else {
      handleClose()
    }
  }

  const handlePrev = () => {
    if (step > 0) setStep(step - 1)
  }

  const handleClose = () => {
    localStorage.setItem(currentUserScopedKey(TOUR_KEY_BASE), 'true')
    setShow(false)
  }

  const handleAction = () => {
    const s = TOUR_STEPS[step]
    if (s.action) {
      handleClose()
      navigate(s.action)
    }
  }

  if (!show) return null

  const current = TOUR_STEPS[step]
  const Icon = current.icon

  return (
    <>
      {/* Backdrop */}
      <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-[100] animate-fade-in" onClick={handleClose} />

      {/* Tour card */}
      <div className="fixed inset-0 z-[101] flex items-center justify-center p-4">
        <div className="glass-card w-full max-w-md p-0 overflow-hidden animate-slide-up shadow-2xl">
          {/* Progress bar */}
          <div className="h-1 bg-surface-800">
            <div
              className={`h-full bg-${current.color} transition-all duration-500`}
              style={{ width: `${((step + 1) / TOUR_STEPS.length) * 100}%` }}
            />
          </div>

          <div className="p-8">
            {/* Close button */}
            <button onClick={handleClose} className="absolute top-4 right-4 text-surface-500 hover:text-white transition-colors">
              <X size={18} />
            </button>

            {/* Icon */}
            <div className={`w-16 h-16 rounded-2xl bg-${current.color}/10 flex items-center justify-center mx-auto mb-6`}>
              <Icon size={32} className={`text-${current.color}`} />
            </div>

            {/* Content */}
            <h2 className="text-xl font-bold text-white text-center mb-2">{current.title}</h2>
            <p className="text-sm text-surface-400 text-center leading-relaxed mb-6">{current.description}</p>

            {/* Step dots */}
            <div className="flex items-center justify-center gap-2 mb-6">
              {TOUR_STEPS.map((_, i) => (
                <div
                  key={i}
                  className={`w-2 h-2 rounded-full transition-all ${
                    i === step ? `bg-${current.color} w-6` : 'bg-surface-700'
                  }`}
                />
              ))}
            </div>

            {/* Navigation */}
            <div className="flex items-center justify-between gap-3">
              {step > 0 ? (
                <button onClick={handlePrev} className="btn-secondary text-sm px-4 py-2 flex items-center gap-1.5">
                  <ArrowLeft size={14} /> Back
                </button>
              ) : (
                <button onClick={handleClose} className="text-sm text-surface-500 hover:text-surface-300 px-3 py-2">
                  Skip tour
                </button>
              )}

              <div className="flex items-center gap-2">
                {current.action && (
                  <button onClick={handleAction} className="btn-secondary text-sm px-4 py-2">
                    Go there →
                  </button>
                )}
                <button onClick={handleNext} className="btn-primary text-sm px-6 py-2 flex items-center gap-1.5">
                  {step === TOUR_STEPS.length - 1 ? 'Get Started' : 'Next'}
                  {step < TOUR_STEPS.length - 1 && <ArrowRight size={14} />}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  )
}
