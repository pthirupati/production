import { useState } from 'react'
import { CheckCircle2, XCircle } from 'lucide-react'

export default function TutorialQuiz({ quiz, onPassed }) {
  const [choice, setChoice] = useState(null)
  const [submitted, setSubmitted] = useState(false)
  if (!quiz?.question || !Array.isArray(quiz.options) || quiz.options.length < 2) return null

  const correct = Number(quiz.answer)
  const passed = submitted && choice === correct

  const submit = () => {
    if (choice == null) return
    setSubmitted(true)
    if (choice === correct) onPassed?.()
  }

  return (
    <div className="mt-5 p-4 rounded-xl border border-accent-cyan/20 bg-accent-cyan/5">
      <p className="text-[10px] font-bold uppercase tracking-wider text-accent-cyan mb-2">Checkpoint</p>
      <p className="text-sm text-white font-medium mb-3">{quiz.question}</p>
      <div className="space-y-2">
        {quiz.options.map((opt, i) => {
          const selected = choice === i
          const showResult = submitted
          const isRight = i === correct
          let cls = 'border-surface-700 hover:border-surface-500'
          if (selected && !showResult) cls = 'border-accent-cyan/50 bg-accent-cyan/10'
          if (showResult && isRight) cls = 'border-accent-green/50 bg-accent-green/10'
          if (showResult && selected && !isRight) cls = 'border-accent-red/50 bg-accent-red/10'
          return (
            <button
              key={i}
              type="button"
              disabled={submitted}
              onClick={() => setChoice(i)}
              className={`w-full text-left text-sm px-3 py-2 rounded-lg border transition-colors ${cls}`}
            >
              {opt}
            </button>
          )
        })}
      </div>
      {!submitted ? (
        <button type="button" className="btn-primary text-xs mt-3" onClick={submit} disabled={choice == null}>
          Check answer
        </button>
      ) : (
        <div className={`mt-3 text-sm flex items-start gap-2 ${passed ? 'text-accent-green' : 'text-accent-amber'}`}>
          {passed ? <CheckCircle2 size={16} className="shrink-0 mt-0.5" /> : <XCircle size={16} className="shrink-0 mt-0.5" />}
          <span>{passed ? (quiz.explanation || 'Correct!') : (quiz.explanation || 'Review the section and try again.')}</span>
        </div>
      )}
    </div>
  )
}
