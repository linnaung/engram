import { useEffect, useState } from 'react'
import { api, type EpisodeItem, type ConceptItem, type FactItem, type BeliefItem } from '../api'

type Tab = 'episodes' | 'concepts' | 'facts' | 'beliefs'

export default function Memories() {
  const [tab, setTab] = useState<Tab>('episodes')
  const [episodes, setEpisodes] = useState<EpisodeItem[]>([])
  const [concepts, setConcepts] = useState<ConceptItem[]>([])
  const [facts, setFacts] = useState<FactItem[]>([])
  const [beliefs, setBeliefs] = useState<BeliefItem[]>([])
  const [search, setSearch] = useState('')

  const load = () => {
    api.episodes().then((r) => setEpisodes(r.episodes))
    api.concepts().then((r) => setConcepts(r.concepts))
    api.facts().then((r) => setFacts(r.facts))
    api.beliefs().then((r) => setBeliefs(r.beliefs))
  }

  useEffect(() => { load() }, [])

  const handleDelete = async (id: string) => { await api.forget(id); load() }

  const tabs: { key: Tab; label: string; count: number }[] = [
    { key: 'episodes', label: 'Episodes', count: episodes.length },
    { key: 'concepts', label: 'Concepts', count: concepts.length },
    { key: 'facts', label: 'Facts', count: facts.length },
    { key: 'beliefs', label: 'Beliefs', count: beliefs.length },
  ]

  const q = search.toLowerCase()

  return (
    <div className="px-6 py-8 space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-black">Memories</h1>
        <input
          type="text" value={search} onChange={(e) => setSearch(e.target.value)}
          placeholder="Filter..."
          className="px-3.5 py-2 border border-neutral-200 rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-black/10 focus:border-neutral-400 transition-colors"
        />
      </div>

      <div className="flex gap-1 border-b border-neutral-200">
        {tabs.map((t) => (
          <button
            key={t.key} onClick={() => setTab(t.key)}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
              tab === t.key ? 'border-black text-black' : 'border-transparent text-neutral-400 hover:text-neutral-600'
            }`}
          >
            {t.label} <span className="text-neutral-300 font-mono">({t.count})</span>
          </button>
        ))}
      </div>

      <div className="bg-white rounded-lg border border-neutral-200 divide-y divide-neutral-100">
        {tab === 'episodes' && episodes.filter((e) => !q || e.content.toLowerCase().includes(q)).map((e) => (
          <div key={e.id} className="flex items-start gap-3 p-4">
            <div className="flex-1 min-w-0">
              <p className="text-sm text-black">{e.content}</p>
              <div className="mt-1.5 flex gap-3 text-xs text-neutral-400">
                <span className="font-mono bg-neutral-100 px-1.5 py-0.5 rounded">{e.source}</span>
                <span>{new Date(e.timestamp).toLocaleString()}</span>
              </div>
            </div>
            <ConfidenceBar value={e.confidence} />
            <button onClick={() => handleDelete(e.id)} className="text-xs text-neutral-300 hover:text-red-500 transition-colors">delete</button>
          </div>
        ))}

        {tab === 'concepts' && concepts.filter((c) => !q || c.summary.toLowerCase().includes(q)).map((c) => (
          <div key={c.id} className="flex items-start gap-3 p-4">
            <div className="flex-1 min-w-0">
              <p className="text-sm text-black">{c.summary}</p>
              <div className="mt-1.5 text-xs text-neutral-400 font-mono">reinforced {c.reinforcement_count}x</div>
            </div>
            <ConfidenceBar value={c.confidence} />
            <button onClick={() => handleDelete(c.id)} className="text-xs text-neutral-300 hover:text-red-500 transition-colors">delete</button>
          </div>
        ))}

        {tab === 'facts' && facts.filter((f) => !q || `${f.subject} ${f.predicate} ${f.object}`.toLowerCase().includes(q)).map((f) => (
          <div key={f.id} className="flex items-start gap-3 p-4">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 text-sm flex-wrap">
                <span className="font-medium text-black">{f.subject}</span>
                {f.subject_type && <span className="text-xs px-1.5 py-0.5 rounded bg-neutral-100 text-neutral-600 font-mono border border-neutral-200">{f.subject_type}</span>}
                <span className="text-neutral-400 font-mono">{f.predicate}</span>
                <span className="font-medium text-black">{f.object}</span>
                {f.object_type && <span className="text-xs px-1.5 py-0.5 rounded bg-neutral-100 text-neutral-600 font-mono border border-neutral-200">{f.object_type}</span>}
              </div>
            </div>
            <ConfidenceBar value={f.confidence} />
            <button onClick={() => handleDelete(f.id)} className="text-xs text-neutral-300 hover:text-red-500 transition-colors">delete</button>
          </div>
        ))}

        {tab === 'beliefs' && beliefs.filter((b) => !q || b.principle.toLowerCase().includes(q)).map((b) => (
          <div key={b.id} className="flex items-start gap-3 p-4">
            <div className="flex-1 min-w-0"><p className="text-sm text-black">{b.principle}</p></div>
            <ConfidenceBar value={b.confidence} />
            <button onClick={() => handleDelete(b.id)} className="text-xs text-neutral-300 hover:text-red-500 transition-colors">delete</button>
          </div>
        ))}

        {((tab === 'episodes' && episodes.filter((e) => !q || e.content.toLowerCase().includes(q)).length === 0) ||
          (tab === 'concepts' && concepts.filter((c) => !q || c.summary.toLowerCase().includes(q)).length === 0) ||
          (tab === 'facts' && facts.filter((f) => !q || `${f.subject} ${f.predicate} ${f.object}`.toLowerCase().includes(q)).length === 0) ||
          (tab === 'beliefs' && beliefs.filter((b) => !q || b.principle.toLowerCase().includes(q)).length === 0)) && (
          <div className="p-10 text-center text-sm text-neutral-400">
            {search ? 'No matches found.' : 'No memories yet. Ingest some data and run synthesis.'}
          </div>
        )}
      </div>
    </div>
  )
}

function ConfidenceBar({ value }: { value: number }) {
  const pct = Math.round(value * 100)
  return (
    <div className="flex items-center gap-2 w-24 flex-shrink-0">
      <div className="flex-1 bg-neutral-100 rounded-full h-1.5">
        <div className="h-1.5 rounded-full bg-black transition-all" style={{ width: `${pct}%`, opacity: Math.max(0.15, value) }} />
      </div>
      <span className="text-xs text-neutral-400 w-8 text-right font-mono">{pct}%</span>
    </div>
  )
}
