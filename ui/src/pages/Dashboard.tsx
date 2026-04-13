import { useEffect, useState } from 'react'
import { api, type Status, type SynthesizeResult, type SimulateStep } from '../api'

function StatCard({ label, value, sub }: { label: string; value: number; sub?: string }) {
  return (
    <div className="bg-white border border-neutral-200 rounded-lg p-5 hover:border-neutral-300 transition-colors">
      <div className="text-[11px] uppercase tracking-wider text-neutral-400 font-medium">{label}</div>
      <div className="text-3xl font-bold text-black mt-1.5 font-mono">{value}</div>
      {sub && <div className="text-[11px] text-neutral-400 mt-1">{sub}</div>}
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

  if (!status) return <div className="text-neutral-400 py-20 text-center text-sm">Loading...</div>

  const maxCount = Math.max(...simSteps.flatMap((s) => [s.episodes, s.concepts, s.facts, s.beliefs]), 1)

  return (
    <div className="px-6 py-8 space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-black">Dashboard</h1>
          <p className="text-sm text-neutral-500 mt-1">Memory system overview</p>
        </div>
        <div className="flex items-center gap-3">
          <span className={`text-xs px-3 py-1.5 rounded-full font-medium border ${status.context_loaded ? 'bg-white text-black border-neutral-300' : 'bg-neutral-50 text-neutral-400 border-neutral-200'}`}>
            {status.context_loaded ? 'Ontology active' : 'No ontology'}
          </span>
          <button
            onClick={handleSynthesize}
            disabled={synthLoading}
            className="px-5 py-2.5 bg-black text-white text-sm font-medium rounded-lg hover:bg-neutral-800 disabled:opacity-50 transition-colors"
          >
            {synthLoading ? 'Synthesizing...' : 'Synthesize'}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        <StatCard label="Episodes" value={status.episodes} sub="L1 raw" />
        <StatCard label="Concepts" value={status.concepts} sub="L2 compressed" />
        <StatCard label="Facts" value={status.facts} sub="L2.5 triples" />
        <StatCard label="Beliefs" value={status.beliefs} sub="L3 principles" />
        <StatCard label="Edges" value={status.edges} sub="Graph links" />
        <StatCard label="Sessions" value={status.sessions} sub="Conversations" />
      </div>

      {synth && (
        <div className="bg-white border border-neutral-200 rounded-lg p-5">
          <h2 className="text-sm font-semibold text-black mb-3">Synthesis Complete</h2>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
            <div><span className="text-neutral-400">Processed:</span> <span className="font-mono font-medium text-black">{synth.episodes_processed}</span></div>
            <div><span className="text-neutral-400">Concepts:</span> <span className="font-mono font-medium text-black">+{synth.concepts_created}</span></div>
            <div><span className="text-neutral-400">Facts:</span> <span className="font-mono font-medium text-black">+{synth.facts_created}</span></div>
            <div><span className="text-neutral-400">Beliefs:</span> <span className="font-mono font-medium text-black">+{synth.beliefs_created}</span></div>
            <div><span className="text-neutral-400">Edges:</span> <span className="font-mono font-medium text-black">+{synth.edges_created}</span></div>
            <div><span className="text-neutral-400">Merged:</span> <span className="font-mono font-medium text-black">{synth.concepts_merged}</span></div>
            <div><span className="text-neutral-400">Contradictions:</span> <span className="font-mono font-medium text-black">{synth.contradictions_resolved}</span></div>
            <div><span className="text-neutral-400">GC'd:</span> <span className="font-mono font-medium text-black">{synth.episodes_garbage_collected}</span></div>
          </div>
        </div>
      )}

      {simSteps.length > 0 && (
        <div className="bg-white border border-neutral-200 rounded-lg p-6">
          <h2 className="text-sm font-semibold text-black mb-5">Memory Decay (365 days)</h2>
          <div className="space-y-1.5">
            {simSteps.map((step) => (
              <div key={step.day} className="flex items-center gap-4 text-xs">
                <span className="w-14 text-right text-neutral-400 font-mono tabular-nums">Day {step.day}</span>
                <div className="flex-1 flex gap-0.5 h-4">
                  {step.episodes > 0 && <div className="bg-black rounded-sm transition-all duration-500" style={{ width: `${(step.episodes / maxCount) * 100}%` }} />}
                  {step.concepts > 0 && <div className="bg-neutral-400 rounded-sm transition-all duration-500" style={{ width: `${(step.concepts / maxCount) * 100}%` }} />}
                  {step.facts > 0 && <div className="bg-neutral-300 rounded-sm transition-all duration-500" style={{ width: `${(step.facts / maxCount) * 100}%` }} />}
                  {step.beliefs > 0 && <div className="bg-neutral-200 rounded-sm transition-all duration-500" style={{ width: `${(step.beliefs / maxCount) * 100}%` }} />}
                </div>
                <span className="w-28 text-neutral-300 font-mono tabular-nums text-[11px]">
                  {step.episodes}/{step.concepts}/{step.facts}/{step.beliefs}
                </span>
              </div>
            ))}
          </div>
          <div className="flex gap-6 mt-5 text-xs text-neutral-400">
            <span className="flex items-center gap-1.5"><span className="w-3 h-3 bg-black rounded-sm" /> Episodes</span>
            <span className="flex items-center gap-1.5"><span className="w-3 h-3 bg-neutral-400 rounded-sm" /> Concepts</span>
            <span className="flex items-center gap-1.5"><span className="w-3 h-3 bg-neutral-300 rounded-sm" /> Facts</span>
            <span className="flex items-center gap-1.5"><span className="w-3 h-3 bg-neutral-200 rounded-sm" /> Beliefs</span>
          </div>
        </div>
      )}
    </div>
  )
}
