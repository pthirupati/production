import { useMemo, useState } from 'react'
import { CheckCircle2, XCircle, RotateCcw, Award } from 'lucide-react'

// Supports two quiz shapes:
//   single:  { question, options[], answer, explanation }
//   module:  { title?, pass_score?, questions: [{ question, options[], answer, explanation }] }
function normalize(quiz) {
  if (!quiz) return null
  if (Array.isArray(quiz.questions) && quiz.questions.length) {
    return {
      title: quiz.title || 'Module quiz',
      passScore: typeof quiz.pass_score === 'number' ? quiz.pass_score : 0.6,
      questions: quiz.questions.filter(
        (q) => q?.question && Array.isArray(q.options) && q.options.length >= 2,
      ),
    }
  }
  if (quiz.question && Array.isArray(quiz.options) && quiz.options.length >= 2) {
    return { title: 'Checkpoint', passScore: 1, questions: [quiz], single: true }
  }
  return null
}

function QuestionBlock({ q, index, total, choice, submitted, onChoose, single }) {
  const correct = Number(q.answer)
  return (
    <div className={index > 0 ? 'mt-5 pt-5 border-t border-surface-800' : ''}>
      {!single && (
        <p className="text-[10px] font-semibold uppercase tracking-wider text-surface-500 mb-1">
          Question {index + 1} of {total}
        </p>
      )}
      <p className="text-sm text-white font-medium mb-3">{q.question}</p>
      <div className="space-y-2">
        {q.options.map((opt, i) => {
          const selected = choice === i
          const isRight = i === correct
          let cls = 'border-surface-700 hover:border-surface-500'
          if (selected && !submitted) cls = 'border-accent-cyan/50 bg-accent-cyan/10'
          if (submitted && isRight) cls = 'border-accent-green/50 bg-accent-green/10'
          if (submitted && selected && !isRight) cls = 'border-accent-red/50 bg-accent-red/10'
          return (
            <button
              key={i}
              type="button"
              disabled={submitted}
              onClick={() => onChoose(i)}
              className={`w-full text-left text-sm px-3 py-2 rounded-lg border transition-colors ${cls}`}
            >
              {opt}
            </button>
          )
        })}
      </div>
      {submitted && (
        <div className={`mt-2.5 text-[13px] flex items-start gap-2 ${choice === correct ? 'text-accent-green' : 'text-accent-amber'}`}>
          {choice === correct
            ? <CheckCircle2 size={15} className="shrink-0 mt-0.5" />
            : <XCircle size={15} className="shrink-0 mt-0.5" />}
          <span>{q.explanation || (choice === correct ? 'Correct!' : 'Review the section and try again.')}</span>
        </div>
      )}
    </div>
  )
}

export default function TutorialQuiz({ quiz, onPassed }) {
  const model = useMemo(() => normalize(quiz), [quiz])
  const [choices, setChoices] = useState({})
  const [submitted, setSubmitted] = useState(false)

  if (!model) return null

  const total = model.questions.length
  const answered = Object.keys(choices).length
  const correctCount = model.questions.reduce(
    (n, q, i) => n + (choices[i] === Number(q.answer) ? 1 : 0),
    0,
  )
  const ratio = total ? correctCount / total : 0
  const passed = submitted && ratio >= model.passScore

  const submit = () => {
    if (answered < total) return
    setSubmitted(true)
    if (correctCount / total >= model.passScore) onPassed?.()
  }

  const retry = () => {
    setChoices({})
    setSubmitted(false)
  }

  return (
    <div className="mt-5 p-4 rounded-xl border border-accent-cyan/20 bg-accent-cyan/5">
      <div className="flex items-center justify-between gap-2 mb-3">
        <p className="text-[10px] font-bold uppercase tracking-wider text-accent-cyan flex items-center gap-1.5">
          <Award size={12} /> {model.single ? 'Checkpoint' : model.title}
        </p>
        {!model.single && !submitted && (
          <span className="text-[10px] text-surface-500">{answered}/{total} answered</span>
        )}
      </div>

      {model.questions.map((q, i) => (
        <QuestionBlock
          key={i}
          q={q}
          index={i}
          total={total}
          choice={choices[i] ?? null}
          submitted={submitted}
          single={model.single}
          onChoose={(c) => setChoices((prev) => ({ ...prev, [i]: c }))}
        />
      ))}

      {!submitted ? (
        <button
          type="button"
          className="btn-primary text-xs mt-4"
          onClick={submit}
          disabled={answered < total}
        >
          {model.single ? 'Check answer' : `Submit quiz (${answered}/${total})`}
        </button>
      ) : (
        <div className="mt-4 flex flex-wrap items-center gap-3">
          {!model.single && (
            <span className={`text-sm font-semibold flex items-center gap-1.5 ${passed ? 'text-accent-green' : 'text-accent-amber'}`}>
              {passed ? <CheckCircle2 size={16} /> : <XCircle size={16} />}
              Score: {correctCount}/{total} ({Math.round(ratio * 100)}%)
              {passed ? ' — passed' : ` — need ${Math.round(model.passScore * 100)}%`}
            </span>
          )}
          {!passed && (
            <button type="button" className="text-xs px-3 py-1.5 rounded-lg border border-surface-700 text-surface-300 hover:text-white hover:border-surface-500 flex items-center gap-1.5" onClick={retry}>
              <RotateCcw size={12} /> Try again
            </button>
          )}
        </div>
      )}
    </div>
  )
}
