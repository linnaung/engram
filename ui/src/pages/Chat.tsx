import { useState, useRef, useEffect, useCallback } from 'react'
import { api, type SessionItem, type MessageItem, type ChatMemory, type SynthesizeResult } from '../api'
import { LogoIcon } from '../components/Logo'

export default function Chat() {
  const [sessions, setSessions] = useState<SessionItem[]>([])
  const [activeId, setActiveId] = useState<string | null>(null)
  const [messages, setMessages] = useState<MessageItem[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [synthLoading, setSynthLoading] = useState(false)
  const [selectedMemories, setSelectedMemories] = useState<ChatMemory[]>([])
  const [synthResult, setSynthResult] = useState<SynthesizeResult | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  const loadSessions = useCallback(() => {
    api.listSessions().then((r) => setSessions(r.sessions))
  }, [])

  useEffect(() => { loadSessions() }, [loadSessions])
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])

  const selectSession = async (id: string) => {
    setActiveId(id)
    setSelectedMemories([])
    setSynthResult(null)
    const data = await api.getSession(id)
    setMessages(data.messages)
  }

  const createSession = async () => {
    const session = await api.createSession()
    loadSessions()
    setActiveId(session.id)
    setMessages([])
    setSelectedMemories([])
  }

  const deleteSession = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation()
    await api.deleteSession(id)
    if (activeId === id) { setActiveId(null); setMessages([]) }
    loadSessions()
  }

  const handleSend = async () => {
    if (!input.trim() || loading || !activeId) return
    const text = input.trim()
    setInput('')
    setLoading(true)

    const tempUser: MessageItem = { id: 'temp-u', role: 'user', content: text, created_at: new Date().toISOString(), memories_used: [] }
    setMessages((m) => [...m, tempUser])

    try {
      const result = await api.sessionChat(activeId, text)
      const assistantMsg: MessageItem = {
        id: 'a-' + Date.now(), role: 'assistant', content: result.response,
        created_at: new Date().toISOString(), memories_used: result.memories_used,
      }
      setMessages((m) => [...m.filter((x) => x.id !== 'temp-u'), { ...tempUser, id: 'u-' + Date.now() }, assistantMsg])
      setSelectedMemories(result.memories_used)
      loadSessions()
    } catch (e: any) {
      setMessages((m) => [...m, { id: 'err', role: 'assistant', content: `Error: ${e.message}`, created_at: new Date().toISOString(), memories_used: [] }])
    } finally {
      setLoading(false)
    }
  }

  const handleSynthesize = async () => {
    setSynthLoading(true)
    setSynthResult(null)
    try { const result = await api.synthesize(); setSynthResult(result) }
    finally { setSynthLoading(false) }
  }

  const layerStyle: Record<string, string> = {
    episode: 'bg-neutral-100 text-neutral-600',
    concept: 'bg-neutral-200 text-neutral-700',
    fact: 'bg-black text-white',
    belief: 'bg-neutral-800 text-white',
  }

  const activeSession = sessions.find((s) => s.id === activeId)

  return (
    <div className="flex h-[calc(100vh-3.5rem)]">
      {/* Session sidebar */}
      <div className="w-64 border-r border-neutral-200 bg-white flex flex-col">
        <div className="p-3 border-b border-neutral-100">
          <button onClick={createSession} className="w-full px-3 py-2.5 text-sm font-medium text-white bg-black rounded-lg hover:bg-neutral-800 transition-colors">
            + New Chat
          </button>
        </div>
        <div className="flex-1 overflow-y-auto">
          {sessions.length === 0 && <p className="text-sm text-neutral-400 text-center py-8 px-4">No conversations yet</p>}
          {sessions.map((s) => (
            <div
              key={s.id}
              onClick={() => selectSession(s.id)}
              className={`group px-4 py-3 cursor-pointer border-b border-neutral-50 transition-colors ${
                activeId === s.id ? 'bg-neutral-50 border-l-2 border-l-black' : 'hover:bg-neutral-50'
              }`}
            >
              <div className="flex items-start justify-between gap-2">
                <div className="flex-1 min-w-0">
                  <div className={`text-sm font-medium truncate ${activeId === s.id ? 'text-black' : 'text-neutral-700'}`}>{s.title}</div>
                  {s.last_message && <div className="text-xs text-neutral-400 truncate mt-0.5">{s.last_message}</div>}
                </div>
                <button onClick={(e) => deleteSession(s.id, e)} className="opacity-0 group-hover:opacity-100 text-neutral-400 hover:text-red-500 transition-all text-xs" title="Delete">x</button>
              </div>
              <div className="text-[11px] text-neutral-300 mt-1 font-mono">{s.message_count} messages</div>
            </div>
          ))}
        </div>
      </div>

      {/* Main chat */}
      <div className="flex-1 flex flex-col bg-stone-50">
        {!activeId ? (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center">
              <div className="mx-auto mb-5 flex justify-center"><LogoIcon size={56} /></div>
              <h2 className="text-xl font-bold text-black mb-2">Engram Chat</h2>
              <p className="text-sm text-neutral-500 mb-6 max-w-sm">Every message is remembered. The assistant recalls relevant memories to inform its responses.</p>
              <button onClick={createSession} className="px-6 py-3 text-sm font-medium text-white bg-black rounded-lg hover:bg-neutral-800 transition-colors">Start New Chat</button>
            </div>
          </div>
        ) : (
          <>
            {/* Header */}
            <div className="px-6 py-3 bg-white border-b border-neutral-200 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <h2 className="text-sm font-semibold text-black truncate max-w-md">{activeSession?.title || 'Chat'}</h2>
                {activeSession?.ontology_path && <span className="text-xs px-2 py-0.5 rounded-full bg-neutral-100 text-neutral-600 border border-neutral-200 font-mono">ontology</span>}
              </div>
              <div className="flex items-center gap-3">
                <label className="text-xs text-neutral-400 hover:text-black cursor-pointer transition-colors">
                  Upload Ontology
                  <input type="file" accept=".ttl,.jsonld" className="hidden" onChange={async (e) => { const file = e.target.files?.[0]; if (file && activeId) { await api.uploadSessionOntology(activeId, file); loadSessions() } }} />
                </label>
                <button onClick={handleSynthesize} disabled={synthLoading} className="px-4 py-1.5 text-xs font-medium bg-black text-white rounded-md hover:bg-neutral-800 disabled:opacity-50 transition-colors">
                  {synthLoading ? 'Synthesizing...' : 'Synthesize'}
                </button>
              </div>
            </div>

            {synthResult && (
              <div className="px-6 py-2 bg-neutral-50 border-b border-neutral-100 text-xs text-neutral-500 flex gap-4 font-mono">
                <span>+{synthResult.concepts_created} concepts</span>
                <span>+{synthResult.facts_created} facts</span>
                <span>+{synthResult.beliefs_created} beliefs</span>
                <span>+{synthResult.edges_created} edges</span>
              </div>
            )}

            {/* Messages */}
            <div className="flex-1 overflow-y-auto px-6 py-5 space-y-5">
              {messages.length === 0 && <p className="text-neutral-400 text-sm text-center py-16">Send a message to start the conversation.</p>}
              {messages.map((msg) => (
                <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  <div className="max-w-xl">
                    <div className={`px-4 py-3 text-sm leading-relaxed ${
                      msg.role === 'user'
                        ? 'bg-black text-white rounded-2xl rounded-br-sm'
                        : 'bg-white text-neutral-800 rounded-2xl rounded-bl-sm border border-neutral-200'
                    }`}>
                      <div className="whitespace-pre-wrap">{msg.content}</div>
                    </div>
                    {msg.role === 'assistant' && msg.memories_used && msg.memories_used.length > 0 && (
                      <button onClick={() => setSelectedMemories(msg.memories_used)} className="mt-1.5 text-xs text-neutral-400 hover:text-black transition-colors flex items-center gap-1.5">
                        <span className="w-1.5 h-1.5 rounded-full bg-black inline-block" />
                        {msg.memories_used.length} memories used
                      </button>
                    )}
                  </div>
                </div>
              ))}
              {loading && (
                <div className="flex justify-start">
                  <div className="bg-white text-neutral-400 px-4 py-3 rounded-2xl rounded-bl-sm border border-neutral-200">
                    <div className="flex gap-1.5">
                      <div className="w-2 h-2 rounded-full bg-neutral-300 animate-bounce" />
                      <div className="w-2 h-2 rounded-full bg-neutral-300 animate-bounce" style={{ animationDelay: '0.15s' }} />
                      <div className="w-2 h-2 rounded-full bg-neutral-300 animate-bounce" style={{ animationDelay: '0.3s' }} />
                    </div>
                  </div>
                </div>
              )}
              <div ref={bottomRef} />
            </div>

            {/* Input */}
            <div className="px-6 py-4 bg-white border-t border-neutral-200">
              <div className="flex gap-2 max-w-3xl mx-auto">
                <input
                  type="text" value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSend()}
                  placeholder="Ask anything..."
                  disabled={loading}
                  className="flex-1 px-4 py-3 bg-neutral-50 border border-neutral-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-black/10 focus:border-neutral-400 disabled:opacity-50 transition-all"
                />
                <button onClick={handleSend} disabled={loading || !input.trim()} className="px-6 py-3 bg-black text-white text-sm font-medium rounded-lg hover:bg-neutral-800 disabled:opacity-30 transition-colors">
                  Send
                </button>
              </div>
            </div>
          </>
        )}
      </div>

      {/* Memory panel */}
      <div className="w-72 border-l border-neutral-200 bg-white flex flex-col">
        <div className="px-4 py-3.5 border-b border-neutral-100">
          <h3 className="text-sm font-semibold text-black">Memory Context</h3>
          <p className="text-xs text-neutral-400 mt-0.5">Click a response to see its memories</p>
        </div>
        <div className="flex-1 overflow-y-auto p-3 space-y-2">
          {selectedMemories.length === 0 && (
            <div className="text-center py-10">
              <div className="w-10 h-10 rounded-lg bg-neutral-100 flex items-center justify-center mx-auto mb-3">
                <span className="text-neutral-400 text-sm font-mono">?</span>
              </div>
              <p className="text-xs text-neutral-400">No memories selected</p>
            </div>
          )}
          {selectedMemories.map((m, i) => (
            <div key={i} className="border border-neutral-200 rounded-lg p-3 hover:border-neutral-300 transition-colors">
              <div className="flex items-center gap-1.5 mb-2">
                <span className={`text-[11px] px-2 py-0.5 rounded font-mono font-medium ${layerStyle[m.layer] || 'bg-neutral-100 text-neutral-500'}`}>
                  {m.layer}
                </span>
                <span className="text-[11px] text-neutral-400 font-mono">{m.score.toFixed(3)}</span>
              </div>
              <p className="text-sm text-neutral-700 leading-relaxed">{m.content}</p>
              <div className="mt-2.5 flex items-center gap-2">
                <div className="flex-1 bg-neutral-100 rounded-full h-1">
                  <div className="h-1 rounded-full bg-black transition-all" style={{ width: `${m.confidence * 100}%`, opacity: Math.max(0.2, m.confidence) }} />
                </div>
                <span className="text-[11px] text-neutral-400 font-mono w-8 text-right">{Math.round(m.confidence * 100)}%</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
