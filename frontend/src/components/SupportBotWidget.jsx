import { useState, useEffect, useRef, useCallback } from 'react'
import { useLocation } from 'react-router-dom'
import { Bot, X, Send, Minimize2, MessageCircle, ThumbsUp, ThumbsDown } from 'lucide-react'
import { supportApi } from '../api/support'
import { useAuthStore } from '../store/authStore'

const STORAGE_KEY = 'fixitlab_support_bot_hidden'

function TypingIndicator({ name }) {
  return (
    <div className="flex items-start gap-2 max-w-[90%]">
      <div className="w-7 h-7 rounded-full fixit-logo-mark flex items-center justify-center shrink-0">
        <Bot size={14} className="text-white" />
      </div>
      <div className="bg-surface-800/90 border border-white/[0.08] rounded-2xl rounded-tl-sm px-4 py-3">
        <p className="text-xs text-surface-500 mb-1.5">{name} is typing</p>
        <div className="flex gap-1">
          <span className="w-2 h-2 rounded-full bg-accent-purple/70 animate-bounce" style={{ animationDelay: '0ms' }} />
          <span className="w-2 h-2 rounded-full bg-accent-cyan/70 animate-bounce" style={{ animationDelay: '150ms' }} />
          <span className="w-2 h-2 rounded-full bg-accent-purple/70 animate-bounce" style={{ animationDelay: '300ms' }} />
        </div>
      </div>
    </div>
  )
}

function BotMessage({ text, name, onFeedback }) {
  const [rated, setRated] = useState(null)

  const rate = (helpful) => {
    if (rated) return
    setRated(helpful ? 'up' : 'down')
    onFeedback?.(helpful)
  }

  return (
    <div className="flex items-start gap-2 max-w-[92%]">
      <div className="w-7 h-7 rounded-full fixit-logo-mark flex items-center justify-center shrink-0 mt-0.5">
        <Bot size={14} className="text-white" />
      </div>
      <div className="bg-surface-800/90 border border-white/[0.08] rounded-2xl rounded-tl-sm px-4 py-2.5">
        <p className="text-[10px] text-accent-cyan/90 font-medium mb-1">{name}</p>
        <p className="text-sm text-surface-200 whitespace-pre-wrap leading-relaxed">{text}</p>
        {onFeedback && (
          <div className="mt-2 pt-1.5 flex items-center gap-2 border-t border-white/[0.06]">
            {rated ? (
              <span className="text-[10px] text-surface-500">
                {rated === 'up' ? 'Thanks for the feedback!' : 'Thanks — we’ll improve this answer.'}
              </span>
            ) : (
              <>
                <span className="text-[10px] text-surface-500">Was this helpful?</span>
                <button
                  type="button"
                  onClick={() => rate(true)}
                  className="p-1 rounded-md text-surface-400 hover:text-accent-cyan hover:bg-surface-700/50 transition-colors"
                  aria-label="Helpful"
                >
                  <ThumbsUp size={13} />
                </button>
                <button
                  type="button"
                  onClick={() => rate(false)}
                  className="p-1 rounded-md text-surface-400 hover:text-accent-purple hover:bg-surface-700/50 transition-colors"
                  aria-label="Not helpful"
                >
                  <ThumbsDown size={13} />
                </button>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

function UserMessage({ text }) {
  return (
    <div className="flex justify-end">
      <div className="max-w-[85%] bg-accent-purple/12 border border-accent-purple/25 rounded-2xl rounded-tr-sm px-4 py-2.5">
        <p className="text-sm text-surface-100 whitespace-pre-wrap">{text}</p>
      </div>
    </div>
  )
}

export default function SupportBotWidget() {
  const { pathname } = useLocation()
  const { isAuthenticated } = useAuthStore()
  const [config, setConfig] = useState(null)
  const [open, setOpen] = useState(false)
  const [fabHidden, setFabHidden] = useState(() => localStorage.getItem(STORAGE_KEY) === '1')
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [typing, setTyping] = useState(false)
  const [suggestions, setSuggestions] = useState([])
  const [sending, setSending] = useState(false)
  const scrollRef = useRef(null)
  const inputRef = useRef(null)

  const loadConfig = useCallback(() => {
    supportApi.getConfig()
      .then((data) => {
        setConfig(data)
        if (data.enabled && data.welcome_message && messages.length === 0) {
          setMessages([{ role: 'bot', text: data.welcome_message }])
          setSuggestions(data.quick_topics?.map((t) => t.prompt) || [])
        }
      })
      .catch(() => setConfig({ enabled: false }))
  }, [messages.length])

  useEffect(() => {
    loadConfig()
  }, [isAuthenticated, loadConfig])

  useEffect(() => {
    const onConfigChange = () => loadConfig()
    window.addEventListener('fixitlab-support-config-changed', onConfigChange)
    return () => window.removeEventListener('fixitlab-support-config-changed', onConfigChange)
  }, [loadConfig])

  useEffect(() => {
    const onOpen = () => {
      setFabHidden(false)
      localStorage.removeItem(STORAGE_KEY)
      setOpen(true)
    }
    window.addEventListener('fixitlab-support-open', onOpen)
    return () => window.removeEventListener('fixitlab-support-open', onOpen)
  }, [])

  useEffect(() => {
    if (open && inputRef.current) {
      setTimeout(() => inputRef.current?.focus(), 100)
    }
  }, [open])

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages, typing, open])

  const sendMessage = async (text) => {
    const trimmed = (text || '').trim()
    if (!trimmed || sending || !config?.enabled) return

    setMessages((prev) => [...prev, { role: 'user', text: trimmed }])
    setInput('')
    setSuggestions([])
    setSending(true)
    setTyping(true)

    try {
      const delay = config.typing_delay_ms || 1200
      const [result] = await Promise.all([
        supportApi.sendMessage(trimmed, pathname),
        new Promise((r) => setTimeout(r, delay)),
      ])
      setTyping(false)
      setMessages((prev) => [...prev, { role: 'bot', text: result.reply, query: trimmed }])
      if (result.suggestions?.length) {
        setSuggestions(result.suggestions)
      }
    } catch (err) {
      setTyping(false)
      const msg = err.response?.data?.error || 'Sorry, I could not reach support right now. Try FAQ or email support.'
      setMessages((prev) => [...prev, { role: 'bot', text: msg }])
    } finally {
      setSending(false)
    }
  }

  const submitFeedback = (botMsg, helpful) => {
    supportApi
      .sendFeedback({
        message: botMsg.query || '',
        reply: botMsg.text || '',
        helpful,
        pagePath: pathname,
      })
      .catch(() => {})
  }

  const hideFab = () => {
    setOpen(false)
    setFabHidden(true)
    localStorage.setItem(STORAGE_KEY, '1')
  }

  if (!config?.enabled) return null

  const botName = config.name || 'FixitLab Assistant'

  return (
    <>
      {/* Chat panel */}
      {open && (
        <div
          className="fixed bottom-20 right-4 sm:right-6 z-[60] w-[min(100vw-2rem,380px)] h-[min(70vh,520px)] flex flex-col fx-panel rounded-2xl p-0 shadow-2xl shadow-black/50 overflow-hidden"
          role="dialog"
          aria-label={`${botName} chat`}
        >
          <div className="shrink-0 flex items-center justify-between px-4 py-3 border-b border-white/[0.08] bg-surface-950/60">
            <div className="flex items-center gap-2.5 min-w-0">
              <div className="w-9 h-9 rounded-xl fixit-logo-mark flex items-center justify-center">
                <Bot size={18} className="text-white" />
              </div>
              <div className="min-w-0">
                <p className="text-sm font-semibold text-white truncate">{botName}</p>
                <p className="text-[10px] text-surface-500">Platform help & how-to</p>
              </div>
            </div>
            <div className="flex items-center gap-1 shrink-0">
              <button
                type="button"
                onClick={() => setOpen(false)}
                className="p-2 rounded-lg text-surface-400 hover:text-white hover:bg-surface-700/50 transition-colors"
                aria-label="Minimize chat"
              >
                <Minimize2 size={16} />
              </button>
              <button
                type="button"
                onClick={hideFab}
                className="p-2 rounded-lg text-surface-400 hover:text-white hover:bg-surface-700/50 transition-colors"
                aria-label="Hide support assistant"
              >
                <X size={16} />
              </button>
            </div>
          </div>

          <div ref={scrollRef} className="flex-1 min-h-0 overflow-y-auto px-4 py-4 space-y-3">
            {messages.map((m, i) =>
              m.role === 'user' ? (
                <UserMessage key={i} text={m.text} />
              ) : (
                <BotMessage
                  key={i}
                  text={m.text}
                  name={botName}
                  onFeedback={m.query ? (helpful) => submitFeedback(m, helpful) : undefined}
                />
              )
            )}
            {typing && <TypingIndicator name={botName} />}
          </div>

          {suggestions.length > 0 && !typing && (
            <div className="shrink-0 px-3 pb-2 flex flex-wrap gap-1.5 max-h-24 overflow-y-auto">
              {suggestions.map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => sendMessage(s)}
                  disabled={sending}
                  className="text-[11px] px-2.5 py-1 rounded-full border border-white/10 text-surface-300 hover:border-accent-purple/40 hover:text-accent-cyan transition-colors"
                >
                  {s.length > 42 ? `${s.slice(0, 40)}…` : s}
                </button>
              ))}
            </div>
          )}

          <form
            className="shrink-0 p-3 border-t border-white/[0.08] bg-surface-950/50"
            onSubmit={(e) => {
              e.preventDefault()
              sendMessage(input)
            }}
          >
            <div className="flex gap-2">
              <input
                ref={inputRef}
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Ask how to use FixitLab…"
                disabled={sending}
                className="input-field flex-1 text-sm py-2.5"
                aria-label="Message to support assistant"
              />
              <button
                type="submit"
                disabled={!input.trim() || sending}
                className="btn-primary px-3 py-2 disabled:opacity-40"
                aria-label="Send message"
              >
                <Send size={16} />
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Floating launcher */}
      {!fabHidden && (
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          className={`fixed bottom-4 right-4 sm:right-6 z-[59] flex items-center gap-2 pl-3 pr-4 py-3 rounded-full shadow-xl transition-all ${
            open
              ? 'bg-surface-800 border border-white/10 text-surface-200'
              : 'fx-support-fab text-white hover:scale-105'
          }`}
          aria-label={open ? 'Close support chat' : 'Open support assistant'}
          aria-expanded={open}
        >
          {open ? <X size={20} /> : <MessageCircle size={20} />}
          {!open && <span className="text-sm font-medium pr-0.5">Help</span>}
        </button>
      )}

      {fabHidden && (
        <button
          type="button"
          onClick={() => {
            setFabHidden(false)
            localStorage.removeItem(STORAGE_KEY)
            setOpen(true)
          }}
          className="fixed bottom-4 right-4 z-[58] p-2.5 rounded-full bg-surface-800/90 border border-surface-600/50 text-surface-400 hover:text-accent-cyan transition-colors"
          aria-label="Show support assistant"
          title="Show help assistant"
        >
          <Bot size={18} />
        </button>
      )}
    </>
  )
}
