import { useEffect, useState } from 'react'
import { api, type Status, type SynthesizeResult, type SimulateStep } from '../api'

function StatCard({ label, value, color, sub }: { label: string; value: number; color: string; sub?: string }) {
  return (
    <div className="bg-white rounded-xl border border-zinc-100 p-4 shadow-sm hover:shadow-md transition-shadow">
      <div className="text-[10px] uppercase tracking-wider text-zinc-400 font-medium">{label}</div>
      <div className={`text-2xl font-bold mt-1 ${color}`}>{value}</div>
      {sub && <div className="text-[10px] text-zinc-400 mt-0.5">{sub}</div>}
    </div>
  )
}

export default function Dashboard() {
  const [status, setStatus] = useState<Status | null>(null)
  const [synth, setSynth] = useState<SynthesizeResult | null>(null)
  const [synthLoading, setSynthLoading] = useState(false)
  const [simSteps, setSimSteps] = useState<SimulateStep[]>([])

  const load = () => {
    api.status().then(setStatus)
    api.simulate(365, 30).then((r) => setSimSteps(r.steps))
  }

  useEffect(() => { load() }, [])

  const handleSynthesize = async () => {
    setSynthLoading(true)
    setSynth(null)
    try {
      const result = await api.synthesize()
      setSynth(result)
      load()
    } finally {
      setSynthLoading(false)
    }
  }

  if (!status) return <div className="text-zinc-400 py-20 text-center text-xs">Loading...</div>

  const maxCount = Math.max(...simSteps.flatMap((s) => [s.episodes, s.concepts, s.facts, s.beliefs]), 1)

  return (
    <div className="px-6 py-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-zinc-900">Dashboard</h1>
          <p className="text-xs text-zinc-400 mt-0.5">Memory system overview</p>
        </div>
        <div className="flex items-center gap-3">
          <span className={`text-[10px] px-2.5 py-1 rounded-full font-medium ${status.context_loaded ? 'bg-emerald-50 text-emerald-600 border border-emerald-200' : 'bg-zinc-50 text-zinc-400 border border-zinc-200'}`}>
            {status.context_loaded ? 'Ontology active' : 'No ontology'}
          </span>
          <button
            onClick={handleSynthesize}
            disabled={synthLoading}
            className="px-4 py-2 bg-indigo-500 text-white text-xs font-medium rounded-lg hover:bg-indigo-600 disabled:opacity-50 transition-colors shadow-sm"
          >
            {synthLoading ? 'Synthesizing...' : 'Synthesize'}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        <StatCard label="Episodes" value={status.episodes} color="text-blue-600" sub="L1 raw" />
        <StatCard label="Concepts" value={status.concepts} color="text-cyan-600" sub="L2 compressed" />
        <StatCard label="Facts" value={status.facts} color="text-emerald-600" sub="L2.5 triples" />
        <StatCard label="Beliefs" value={status.beliefs} color="text-violet-600" sub="L3 principles" />
        <StatCard label="Edges" value={status.edges} color="text-orange-500" sub="Graph links" />
        <StatCard label="Sessions" value={status.sessions} color="text-zinc-700" sub="Conversations" />
      </div>

      {synth && (
        <div className="bg-indigo-50 rounded-xl border border-indigo-100 p-4">
          <h2 className="text-xs font-semibold text-indigo-900 mb-2">Synthesis Complete</h2>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px]">
            <div><span className="text-indigo-400">Processed:</span> <span className="font-semibold text-indigo-900">{synth.episodes_processed}</span></div>
            <div><span className="text-indigo-400">Concepts:</span> <span className="font-semibold text-indigo-900">+{synth.concepts_created}</span></div>
            <div><span className="text-indigo-400">Facts:</span> <span className="font-semibold text-indigo-900">+{synth.facts_created}</span></div>
            <div><span className="text-indigo-400">Beliefs:</span> <span className="font-semibold text-indigo-900">+{synth.beliefs_created}</span></div>
            <div><span className="text-indigo-400">Edges:</span> <span className="font-semibold text-indigo-900">+{synth.edges_created}</span></div>
            <div><span className="text-indigo-400">Merged:</span> <span className="font-semibold text-indigo-900">{synth.concepts_merged}</span></div>
            <div><span className="text-indigo-400">Contradictions:</span> <span className="font-semibold text-indigo-900">{synth.contradictions_resolved}</span></div>
            <div><span className="text-indigo-400">GC'd:</span> <span className="font-semibold text-indigo-900">{synth.episodes_garbage_collected}</span></div>
          </div>
        </div>
      )}

      {simSteps.length > 0 && (
        <div className="bg-white rounded-xl border border-zinc-100 p-5 shadow-sm">
          <h2 className="text-xs font-semibold text-zinc-800 mb-4">Memory Decay (365 days)</h2>
          <div className="space-y-1.5">
            {simSteps.map((step) => (
              <div key={step.day} className="flex items-center gap-3 text-[10px]">
                <span className="w-12 text-right text-zinc-400 font-mono tabular-nums">Day {step.day}</span>
                <div className="flex-1 flex gap-0.5 h-4">
                  {step.episodes > 0 && <div className="bg-blue-400 rounded-sm transition-all duration-500" style={{ width: `${(step.episodes / maxCount) * 100}%` }} />}
                  {step.concepts > 0 && <div className="bg-cyan-400 rounded-sm transition-all duration-500" style={{ width: `${(step.concepts / maxCount) * 100}%` }} />}
                  {step.facts > 0 && <div className="bg-emerald-400 rounded-sm transition-all duration-500" style={{ width: `${(step.facts / maxCount) * 100}%` }} />}
                  {step.beliefs > 0 && <div className="bg-violet-400 rounded-sm transition-all duration-500" style={{ width: `${(step.beliefs / maxCount) * 100}%` }} />}
                </div>
                <span className="w-28 text-zinc-300 font-mono tabular-nums">
                  {step.episodes}/{step.concepts}/{step.facts}/{step.beliefs}
                </span>
              </div>
            ))}
          </div>
          <div className="flex gap-5 mt-4 text-[10px] text-zinc-400">
            <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 bg-blue-400 rounded-sm" /> Episodes</span>
            <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 bg-cyan-400 rounded-sm" /> Concepts</span>
            <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 bg-emerald-400 rounded-sm" /> Facts</span>
            <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 bg-violet-400 rounded-sm" /> Beliefs</span>
          </div>
        </div>
      )}
    </div>
  )
}
