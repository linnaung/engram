import { useEffect, useState } from 'react'
import { api, type EpisodeItem, type ConceptItem, type FactItem, type BeliefItem } from '../api'

type Tab = 'episodes' | 'concepts' | 'facts' | 'beliefs'

const layerColors: Record<Tab, { bg: string; text: string; border: string }> = {
  episodes: { bg: 'bg-blue-50', text: 'text-blue-600', border: 'border-blue-100' },
  concepts: { bg: 'bg-cyan-50', text: 'text-cyan-600', border: 'border-cyan-100' },
  facts: { bg: 'bg-emerald-50', text: 'text-emerald-600', border: 'border-emerald-100' },
  beliefs: { bg: 'bg-violet-50', text: 'text-violet-600', border: 'border-violet-100' },
}

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

  const handleDelete = async (id: string) => {
    await api.forget(id)
    load()
  }

  const tabs: { key: Tab; label: string; count: number }[] = [
    { key: 'episodes', label: 'Episodes', count: episodes.length },
    { key: 'concepts', label: 'Concepts', count: concepts.length },
    { key: 'facts', label: 'Facts', count: facts.length },
    { key: 'beliefs', label: 'Beliefs', count: beliefs.length },
  ]

  const q = search.toLowerCase()

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-zinc-900">Memories</h1>
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Filter..."
          className="px-3 py-1.5 border border-zinc-200 rounded-lg text-xs text-zinc-900 placeholder:text-zinc-300 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-400 transition-colors"
        />
      </div>

      <div className="flex gap-1 border-b border-zinc-100">
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`px-4 py-2 text-xs font-medium border-b-2 transition-colors ${
              tab === t.key
                ? 'border-indigo-500 text-indigo-600'
                : 'border-transparent text-zinc-400 hover:text-zinc-600'
            }`}
          >
            {t.label} <span className="text-zinc-300">({t.count})</span>
          </button>
        ))}
      </div>

      <div className="bg-white rounded-xl border border-zinc-100 shadow-sm divide-y divide-zinc-50">
        {tab === 'episodes' && episodes
          .filter((e) => !q || e.content.toLowerCase().includes(q))
          .map((e) => (
            <div key={e.id} className="flex items-start gap-3 p-4">
              <div className="flex-1 min-w-0">
                <p className="text-xs text-zinc-900">{e.content}</p>
                <div className="mt-1.5 flex gap-3 text-[10px] text-zinc-400">
                  <span className={`px-1.5 py-0.5 rounded ${layerColors.episodes.bg} ${layerColors.episodes.text} ${layerColors.episodes.border} border`}>{e.source}</span>
                  <span>{new Date(e.timestamp).toLocaleString()}</span>
                </div>
              </div>
              <ConfidenceBar value={e.confidence} />
              <button onClick={() => handleDelete(e.id)} className="text-[10px] text-zinc-300 hover:text-red-500 transition-colors">delete</button>
            </div>
          ))}

        {tab === 'concepts' && concepts
          .filter((c) => !q || c.summary.toLowerCase().includes(q))
          .map((c) => (
            <div key={c.id} className="flex items-start gap-3 p-4">
              <div className="flex-1 min-w-0">
                <p className="text-xs text-zinc-900">{c.summary}</p>
                <div className="mt-1.5 text-[10px] text-zinc-400">
                  reinforced {c.reinforcement_count}x
                </div>
              </div>
              <ConfidenceBar value={c.confidence} />
              <button onClick={() => handleDelete(c.id)} className="text-[10px] text-zinc-300 hover:text-red-500 transition-colors">delete</button>
            </div>
          ))}

        {tab === 'facts' && facts
          .filter((f) => !q || `${f.subject} ${f.predicate} ${f.object}`.toLowerCase().includes(q))
          .map((f) => (
            <div key={f.id} className="flex items-start gap-3 p-4">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 text-xs flex-wrap">
                  <span className="font-medium text-zinc-900">{f.subject}</span>
                  {f.subject_type && <span className={`text-[10px] px-1.5 py-0.5 rounded ${layerColors.facts.bg} ${layerColors.facts.text} border ${layerColors.facts.border}`}>{f.subject_type}</span>}
                  <span className="text-zinc-400">{f.predicate}</span>
                  <span className="font-medium text-zinc-900">{f.object}</span>
                  {f.object_type && <span className={`text-[10px] px-1.5 py-0.5 rounded ${layerColors.facts.bg} ${layerColors.facts.text} border ${layerColors.facts.border}`}>{f.object_type}</span>}
                </div>
              </div>
              <ConfidenceBar value={f.confidence} />
              <button onClick={() => handleDelete(f.id)} className="text-[10px] text-zinc-300 hover:text-red-500 transition-colors">delete</button>
            </div>
          ))}

        {tab === 'beliefs' && beliefs
          .filter((b) => !q || b.principle.toLowerCase().includes(q))
          .map((b) => (
            <div key={b.id} className="flex items-start gap-3 p-4">
              <div className="flex-1 min-w-0">
                <p className="text-xs text-zinc-900">{b.principle}</p>
              </div>
              <ConfidenceBar value={b.confidence} />
              <button onClick={() => handleDelete(b.id)} className="text-[10px] text-zinc-300 hover:text-red-500 transition-colors">delete</button>
            </div>
          ))}

        {((tab === 'episodes' && episodes.filter((e) => !q || e.content.toLowerCase().includes(q)).length === 0) ||
          (tab === 'concepts' && concepts.filter((c) => !q || c.summary.toLowerCase().includes(q)).length === 0) ||
          (tab === 'facts' && facts.filter((f) => !q || `${f.subject} ${f.predicate} ${f.object}`.toLowerCase().includes(q)).length === 0) ||
          (tab === 'beliefs' && beliefs.filter((b) => !q || b.principle.toLowerCase().includes(q)).length === 0)) && (
          <div className="p-8 text-center text-xs text-zinc-400">
            {search ? 'No matches found.' : 'No memories yet. Ingest some data and run synthesis.'}
          </div>
        )}
      </div>
    </div>
  )
}

function ConfidenceBar({ value }: { value: number }) {
  const pct = Math.round(value * 100)
  const color = pct > 70 ? 'bg-emerald-400' : pct > 40 ? 'bg-amber-400' : 'bg-red-400'
  return (
    <div className="flex items-center gap-2 w-24 flex-shrink-0">
      <div className="flex-1 bg-zinc-100 rounded-full h-1">
        <div className={`${color} h-1 rounded-full transition-all`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-[10px] text-zinc-400 w-8 text-right">{pct}%</span>
    </div>
  )
}
