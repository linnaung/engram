import { useEffect, useRef, useState } from 'react'
import { api, type BeliefItem, type EdgeItem, type FactItem } from '../api'

export default function Graph() {
  const containerRef = useRef<HTMLDivElement>(null)
  const [beliefs, setBeliefs] = useState<BeliefItem[]>([])
  const [edges, setEdges] = useState<EdgeItem[]>([])
  const [facts, setFacts] = useState<FactItem[]>([])
  const [selected, setSelected] = useState<BeliefItem | FactItem | null>(null)
  const networkRef = useRef<any>(null)

  useEffect(() => {
    api.beliefs().then((r) => { setBeliefs(r.beliefs); setEdges(r.edges) })
    api.facts().then((r) => setFacts(r.facts))
  }, [])

  useEffect(() => {
    if (!containerRef.current || (beliefs.length === 0 && facts.length === 0)) return

    const loadVis = async () => {
      const vis = await import('vis-network/standalone')

      const nodes: any[] = []
      const visEdges: any[] = []

      beliefs.forEach((b) => {
        nodes.push({
          id: b.id,
          label: b.principle.length > 40 ? b.principle.slice(0, 40) + '...' : b.principle,
          title: `${b.principle}\n\nConfidence: ${b.confidence}`,
          value: b.confidence * 10,
          color: { background: '#8b5cf6', border: '#7c3aed' },
          font: { color: '#18181b' },
          shape: 'dot',
        })
      })

      facts.forEach((f) => {
        const nodeId = `fact:${f.id}`
        nodes.push({
          id: nodeId,
          label: `${f.subject} ${f.predicate} ${f.object}`,
          title: `${f.subject} [${f.subject_type}] ${f.predicate} ${f.object} [${f.object_type}]\nConfidence: ${f.confidence}`,
          value: f.confidence * 6,
          color: { background: '#10b981', border: '#059669' },
          font: { color: '#18181b', size: 11 },
          shape: 'box',
        })
      })

      edges.forEach((e) => {
        visEdges.push({
          from: e.source,
          to: e.target,
          label: e.relation,
          value: e.weight,
          color: { color: '#a1a1aa', highlight: '#52525b' },
          font: { color: '#71717a', size: 10 },
          arrows: { to: { enabled: true, scaleFactor: 0.7 } },
          smooth: { type: 'continuous' },
        })
      })

      const data = {
        nodes: new vis.DataSet(nodes),
        edges: new vis.DataSet(visEdges),
      }

      const options = {
        physics: {
          barnesHut: { gravitationalConstant: -2000, centralGravity: 0.15, springLength: 150 },
          stabilization: { iterations: 100 },
        },
        interaction: { hover: true, tooltipDelay: 100 },
      }

      const network = new vis.Network(containerRef.current!, data, options)
      networkRef.current = network

      network.on('click', (params: any) => {
        if (params.nodes.length > 0) {
          const nodeId = params.nodes[0]
          if (typeof nodeId === 'string' && nodeId.startsWith('fact:')) {
            const factId = nodeId.replace('fact:', '')
            const f = facts.find((x) => x.id === factId)
            if (f) setSelected(f)
          } else {
            const b = beliefs.find((x) => x.id === nodeId)
            if (b) setSelected(b)
          }
        } else {
          setSelected(null)
        }
      })
    }

    loadVis()

    return () => { networkRef.current?.destroy() }
  }, [beliefs, edges, facts])

  const isBelief = (item: any): item is BeliefItem => 'principle' in item
  const isFact = (item: any): item is FactItem => 'predicate' in item

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-zinc-900">Memory Graph</h1>
        <div className="flex gap-3 text-[10px] text-zinc-400">
          <span className="flex items-center gap-1">
            <span className="w-2.5 h-2.5 rounded-full bg-violet-500 inline-block" /> Beliefs ({beliefs.length})
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2.5 h-2.5 rounded bg-emerald-500 inline-block" /> Facts ({facts.length})
          </span>
          <span>{edges.length} edges</span>
        </div>
      </div>

      <div className="flex gap-3" style={{ height: 'calc(100vh - 12rem)' }}>
        <div
          ref={containerRef}
          className="flex-1 bg-white rounded-xl border border-zinc-100 shadow-sm"
        />

        {selected && (
          <div className="w-72 bg-white rounded-xl border border-zinc-100 shadow-sm p-4 overflow-y-auto">
            {isBelief(selected) && (
              <>
                <span className="text-[10px] px-2 py-0.5 rounded-md bg-violet-50 text-violet-600 font-medium border border-violet-100">Belief</span>
                <p className="mt-3 text-xs text-zinc-900">{selected.principle}</p>
                <div className="mt-3 text-[10px] text-zinc-400 space-y-0.5">
                  <div>ID: {selected.id.slice(0, 8)}</div>
                  <div>Confidence: {selected.confidence}</div>
                </div>
              </>
            )}
            {isFact(selected) && (
              <>
                <span className="text-[10px] px-2 py-0.5 rounded-md bg-emerald-50 text-emerald-600 font-medium border border-emerald-100">Fact</span>
                <div className="mt-3 space-y-2 text-xs">
                  <div><span className="text-zinc-400">Subject:</span> <span className="text-zinc-900">{selected.subject}</span> {selected.subject_type && <span className="text-[10px] text-zinc-400">[{selected.subject_type}]</span>}</div>
                  <div><span className="text-zinc-400">Predicate:</span> <span className="text-zinc-900 font-medium">{selected.predicate}</span></div>
                  <div><span className="text-zinc-400">Object:</span> <span className="text-zinc-900">{selected.object}</span> {selected.object_type && <span className="text-[10px] text-zinc-400">[{selected.object_type}]</span>}</div>
                </div>
                <div className="mt-3 text-[10px] text-zinc-400">
                  <div>Confidence: {selected.confidence}</div>
                </div>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
