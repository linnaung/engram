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
    if (activeId === id) {
      setActiveId(null)
      setMessages([])
    }
    loadSessions()
  }

  const handleSend = async () => {
    if (!input.trim() || loading || !activeId) return
    const text = input.trim()
    setInput('')
    setLoading(true)

    // Optimistic UI
    const tempUser: MessageItem = { id: 'temp-u', role: 'user', content: text, created_at: new Date().toISOString(), memories_used: [] }
    setMessages((m) => [...m, tempUser])

    try {
      const result = await api.sessionChat(activeId, text)
      const assistantMsg: MessageItem = {
        id: 'temp-a-' + Date.now(),
        role: 'assistant',
        content: result.response,
        created_at: new Date().toISOString(),
        memories_used: result.memories_used,
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
    try {
      const result = await api.synthesize()
      setSynthResult(result)
    } finally {
      setSynthLoading(false)
    }
  }

  const layerStyle: Record<string, string> = {
    episode: 'bg-blue-50 text-blue-600 border-blue-200',
    concept: 'bg-cyan-50 text-cyan-600 border-cyan-200',
    fact: 'bg-emerald-50 text-emerald-600 border-emerald-200',
    belief: 'bg-violet-50 text-violet-600 border-violet-200',
  }

  const activeSession = sessions.find((s) => s.id === activeId)

  return (
    <div className="flex h-[calc(100vh-3rem)]">
      {/* Session sidebar */}
      <div className="w-64 border-r border-zinc-200/80 bg-white flex flex-col">
        <div className="p-3 border-b border-zinc-100">
          <button
            onClick={createSession}
            className="w-full px-3 py-2 text-xs font-medium text-white bg-zinc-900 rounded-lg hover:bg-zinc-800 transition-colors"
          >
            + New Chat
          </button>
        </div>
        <div className="flex-1 overflow-y-auto">
          {sessions.length === 0 && (
            <p className="text-xs text-zinc-400 text-center py-8 px-4">
              No conversations yet
            </p>
          )}
          {sessions.map((s) => (
            <div
              key={s.id}
              onClick={() => selectSession(s.id)}
              className={`group px-3 py-2.5 cursor-pointer border-b border-zinc-50 transition-colors ${
                activeId === s.id ? 'bg-indigo-50 border-l-2 border-l-indigo-500' : 'hover:bg-zinc-50'
              }`}
            >
              <div className="flex items-start justify-between gap-2">
                <div className="flex-1 min-w-0">
                  <div className={`text-xs font-medium truncate ${activeId === s.id ? 'text-indigo-900' : 'text-zinc-800'}`}>
                    {s.title}
                  </div>
                  {s.last_message && (
                    <div className="text-[10px] text-zinc-400 truncate mt-0.5">
                      {s.last_message}
                    </div>
                  )}
                </div>
                <button
                  onClick={(e) => deleteSession(s.id, e)}
                  className="opacity-0 group-hover:opacity-100 text-zinc-400 hover:text-red-500 transition-all text-xs p-0.5"
                  title="Delete"
                >
                  x
                </button>
              </div>
              <div className="text-[10px] text-zinc-300 mt-1">
                {s.message_count} messages
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Main chat area */}
      <div className="flex-1 flex flex-col bg-zinc-50">
        {!activeId ? (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center">
              <div className="mx-auto mb-4 flex justify-center">
                <LogoIcon size={48} />
              </div>
              <h2 className="text-lg font-semibold text-zinc-800 mb-1">Engram Chat</h2>
              <p className="text-xs text-zinc-400 mb-4 max-w-xs">
                Every message is remembered. The assistant recalls relevant memories to inform its responses.
              </p>
              <button
                onClick={createSession}
                className="px-4 py-2 text-xs font-medium text-white bg-indigo-500 rounded-lg hover:bg-indigo-600 transition-colors"
              >
                Start New Chat
              </button>
            </div>
          </div>
        ) : (
          <>
            {/* Session header */}
            <div className="px-5 py-3 bg-white border-b border-zinc-200/80 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <h2 className="text-sm font-semibold text-zinc-800 truncate max-w-md">
                  {activeSession?.title || 'Chat'}
                </h2>
                {activeSession?.ontology_path && (
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-600 border border-emerald-200">
                    Ontology
                  </span>
                )}
              </div>
              <div className="flex items-center gap-2">
                <label className="text-[10px] text-zinc-400 hover:text-indigo-500 cursor-pointer transition-colors">
                  Upload Ontology
                  <input
                    type="file"
                    accept=".ttl,.jsonld"
                    className="hidden"
                    onChange={async (e) => {
                      const file = e.target.files?.[0]
                      if (file && activeId) {
                        await api.uploadSessionOntology(activeId, file)
                        loadSessions()
                      }
                    }}
                  />
                </label>
                <button
                  onClick={handleSynthesize}
                  disabled={synthLoading}
                  className="px-3 py-1 text-[10px] font-medium bg-zinc-900 text-white rounded-md hover:bg-zinc-800 disabled:opacity-50 transition-colors"
                >
                  {synthLoading ? 'Synthesizing...' : 'Synthesize'}
                </button>
              </div>
            </div>

            {synthResult && (
              <div className="px-5 py-2 bg-indigo-50 border-b border-indigo-100 text-[10px] text-indigo-700 flex gap-4">
                <span>+{synthResult.concepts_created} concepts</span>
                <span>+{synthResult.facts_created} facts</span>
                <span>+{synthResult.beliefs_created} beliefs</span>
                <span>+{synthResult.edges_created} edges</span>
                {synthResult.concepts_merged > 0 && <span>{synthResult.concepts_merged} merged</span>}
              </div>
            )}

            {/* Messages */}
            <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
              {messages.length === 0 && (
                <p className="text-zinc-400 text-xs text-center py-16">
                  Send a message to start the conversation.
                </p>
              )}
              {messages.map((msg) => (
                <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  <div className={`max-w-xl group ${msg.role === 'user' ? 'items-end' : 'items-start'}`}>
                    <div
                      className={`px-4 py-2.5 text-[13px] leading-relaxed ${
                        msg.role === 'user'
                          ? 'bg-zinc-900 text-white rounded-2xl rounded-br-md'
                          : 'bg-white text-zinc-800 rounded-2xl rounded-bl-md shadow-sm border border-zinc-100'
                      }`}
                    >
                      <div className="whitespace-pre-wrap">{msg.content}</div>
                    </div>
                    {msg.role === 'assistant' && msg.memories_used && msg.memories_used.length > 0 && (
                      <button
                        onClick={() => setSelectedMemories(msg.memories_used)}
                        className="mt-1 text-[10px] text-zinc-400 hover:text-indigo-500 transition-colors flex items-center gap-1"
                      >
                        <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 inline-block" />
                        {msg.memories_used.length} memories used
                      </button>
                    )}
                  </div>
                </div>
              ))}
              {loading && (
                <div className="flex justify-start">
                  <div className="bg-white text-zinc-400 px-4 py-3 rounded-2xl rounded-bl-md shadow-sm border border-zinc-100 text-xs">
                    <div className="flex gap-1">
                      <div className="w-1.5 h-1.5 rounded-full bg-zinc-300 animate-bounce" />
                      <div className="w-1.5 h-1.5 rounded-full bg-zinc-300 animate-bounce" style={{ animationDelay: '0.15s' }} />
                      <div className="w-1.5 h-1.5 rounded-full bg-zinc-300 animate-bounce" style={{ animationDelay: '0.3s' }} />
                    </div>
                  </div>
                </div>
              )}
              <div ref={bottomRef} />
            </div>

            {/* Input */}
            <div className="px-5 py-3 bg-white border-t border-zinc-200/80">
              <div className="flex gap-2 max-w-3xl mx-auto">
                <input
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSend()}
                  placeholder="Ask anything..."
                  disabled={loading}
                  className="flex-1 px-4 py-2.5 bg-zinc-50 border border-zinc-200 rounded-xl text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-300 disabled:opacity-50 transition-all"
                />
                <button
                  onClick={handleSend}
                  disabled={loading || !input.trim()}
                  className="px-5 py-2.5 bg-indigo-500 text-white text-xs font-medium rounded-xl hover:bg-indigo-600 disabled:opacity-40 transition-colors shadow-sm"
                >
                  Send
                </button>
              </div>
            </div>
          </>
        )}
      </div>

      {/* Memory panel */}
      <div className="w-72 border-l border-zinc-200/80 bg-white flex flex-col">
        <div className="px-4 py-3 border-b border-zinc-100">
          <h3 className="text-xs font-semibold text-zinc-800">Memory Context</h3>
          <p className="text-[10px] text-zinc-400 mt-0.5">Click a response to see its memories</p>
        </div>
        <div className="flex-1 overflow-y-auto p-3 space-y-2">
          {selectedMemories.length === 0 && (
            <div className="text-center py-8">
              <div className="w-8 h-8 rounded-lg bg-zinc-100 flex items-center justify-center mx-auto mb-2">
                <span className="text-zinc-400 text-xs">?</span>
              </div>
              <p className="text-[10px] text-zinc-400">No memories selected</p>
            </div>
          )}
          {selectedMemories.map((m, i) => (
            <div key={i} className="rounded-lg border border-zinc-100 p-3 hover:border-zinc-200 transition-colors">
              <div className="flex items-center gap-1.5 mb-2">
                <span className={`text-[10px] px-1.5 py-0.5 rounded-md border font-medium ${layerStyle[m.layer] || 'bg-zinc-50 text-zinc-500 border-zinc-200'}`}>
                  {m.layer}
                </span>
                <span className="text-[10px] text-zinc-400">{m.score.toFixed(3)}</span>
              </div>
              <p className="text-[11px] text-zinc-700 leading-relaxed">{m.content}</p>
              <div className="mt-2 flex items-center gap-2">
                <div className="flex-1 bg-zinc-100 rounded-full h-1">
                  <div
                    className={`h-1 rounded-full transition-all ${m.confidence > 0.7 ? 'bg-emerald-400' : m.confidence > 0.4 ? 'bg-amber-400' : 'bg-red-400'}`}
                    style={{ width: `${m.confidence * 100}%` }}
                  />
                </div>
                <span className="text-[9px] text-zinc-400">{Math.round(m.confidence * 100)}%</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
