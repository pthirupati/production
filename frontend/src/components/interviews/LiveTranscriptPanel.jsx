/**
 * LiveTranscriptPanel.jsx
 *
 * Real-time transcript display with:
 * - Interviewer messages (TTS text, highlighted)
 * - Candidate messages (final + interim/live text)
 * - STAR coaching hints inline
 * - Score badges on submitted answers
 * - Auto-scroll to latest message
 */

import React, { useEffect, useRef } from 'react'

// ---------------------------------------------------------------------------
// Score badge
// ---------------------------------------------------------------------------

function ScoreBadge({ score }) {
  if (score == null) return null
  const pct = Math.round(score)
  const cls =
    pct >= 75 ? 'bg-green-900 text-green-300 border-green-700' :
    pct >= 50 ? 'bg-amber-900 text-amber-300 border-amber-700' :
                'bg-red-900 text-red-300 border-red-700'
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium border ml-2 ${cls}`}>
      {pct}/100
    </span>
  )
}

// ---------------------------------------------------------------------------
// STAR coaching hint
// ---------------------------------------------------------------------------

function StarHint({ starData }) {
  if (!starData || !starData.coaching_note) return null
  return (
    <div className="mt-1 text-xs text-amber-400 italic">
      Tip: {starData.coaching_note}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Message bubble
// ---------------------------------------------------------------------------

function MessageBubble({ message, isInterim = false }) {
  const isInterviewer = message.role === 'interviewer' || message.role === 'system'

  if (message.role === 'system') {
    return (
      <div className="flex justify-center my-1">
        <span className="text-xs text-slate-500 italic bg-slate-900 px-3 py-1 rounded-full border border-slate-700">
          {message.content}
        </span>
      </div>
    )
  }

  const bubbleClass = isInterviewer
    ? 'bg-slate-800 border border-slate-600 text-slate-100 rounded-tl-none'
    : isInterim
      ? 'bg-blue-950 border border-blue-700 text-blue-200 rounded-tr-none opacity-80 italic'
      : 'bg-blue-900 border border-blue-700 text-white rounded-tr-none'

  const labelClass = isInterviewer ? 'text-indigo-400' : 'text-blue-400'
  const label = isInterviewer
    ? (message.persona_name || 'Interviewer')
    : (isInterim ? 'You (listening...)' : 'You')

  const typeLabel = {
    introduction: 'Opening',
    question: 'Question',
    practical: 'Practical',
    follow_up: 'Follow-up',
    av_warning: 'AV Warning',
  }[message.message_type] || null

  return (
    <div className={`flex ${isInterviewer ? 'justify-start' : 'justify-end'} mb-3`}>
      <div className={`max-w-[85%] rounded-2xl px-4 py-3 shadow-sm ${bubbleClass}`}>
        <div className="flex items-center gap-2 mb-1 flex-wrap">
          <span className={`text-xs font-semibold ${labelClass}`}>{label}</span>
          {typeLabel && (
            <span className="text-xs text-slate-500 bg-slate-900 px-1.5 py-0.5 rounded">
              {typeLabel}
            </span>
          )}
          {!isInterim && <ScoreBadge score={message.score} />}
        </div>
        <p className="text-sm leading-relaxed whitespace-pre-wrap break-words">
          {message.content}
        </p>
        {!isInterim && message.metadata?.star_analysis && (
          <StarHint starData={message.metadata.star_analysis} />
        )}
        {!isInterim && message.metadata?.feedback && (
          <p className="text-xs text-slate-400 mt-1 italic">{message.metadata.feedback}</p>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Typing indicator (when interviewer reply is pending)
// ---------------------------------------------------------------------------

function TypingIndicator({ personaName }) {
  return (
    <div className="flex justify-start mb-3">
      <div className="bg-slate-800 border border-slate-600 rounded-2xl rounded-tl-none px-4 py-3">
        <span className="text-xs text-indigo-400 font-semibold block mb-1">{personaName || 'Interviewer'}</span>
        <div className="flex gap-1 items-center">
          {[0, 1, 2].map(i => (
            <span
              key={i}
              className="w-2 h-2 bg-slate-400 rounded-full animate-bounce"
              style={{ animationDelay: `${i * 0.15}s` }}
            />
          ))}
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main panel
// ---------------------------------------------------------------------------

export default function LiveTranscriptPanel({
  messages = [],
  interimTranscript = '',
  isInterviewerTyping = false,
  personaName = 'Interviewer',
  className = '',
}) {
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages.length, interimTranscript, isInterviewerTyping])

  return (
    <div className={`flex flex-col h-full bg-slate-950 ${className}`}>
      {/* Header */}
      <div className="px-4 py-2.5 border-b border-slate-800 shrink-0">
        <h3 className="text-white font-semibold text-sm">Live Transcript</h3>
        <p className="text-slate-500 text-xs">Real-time conversation</p>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-1">
        {messages.length === 0 && (
          <div className="flex items-center justify-center h-full">
            <p className="text-slate-600 text-sm">Transcript will appear here...</p>
          </div>
        )}

        {messages.map((msg, i) => (
          <MessageBubble key={msg.id || i} message={msg} />
        ))}

        {/* Live interim transcript */}
        {interimTranscript && (
          <MessageBubble
            message={{ role: 'candidate', content: interimTranscript, message_type: 'text' }}
            isInterim
          />
        )}

        {/* Interviewer typing indicator */}
        {isInterviewerTyping && <TypingIndicator personaName={personaName} />}

        <div ref={bottomRef} />
      </div>
    </div>
  )
}
