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
          color: { background: '#000', border: '#000' },
          font: { color: '#000', size: 13, face: 'Inter' },
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
          color: { background: '#d4d4d4', border: '#a3a3a3' },
          font: { color: '#000', size: 11, face: 'IBM Plex Mono' },
          shape: 'box',
        })
      })

      edges.forEach((e) => {
        visEdges.push({
          from: e.source, to: e.target, label: e.relation, value: e.weight,
          color: { color: '#d4d4d4', highlight: '#000' },
          font: { color: '#a3a3a3', size: 10, face: 'IBM Plex Mono' },
          arrows: { to: { enabled: true, scaleFactor: 0.7 } },
          smooth: { type: 'continuous' },
        })
      })

      const network = new vis.Network(containerRef.current!, {
        nodes: new vis.DataSet(nodes), edges: new vis.DataSet(visEdges),
      }, {
        physics: { barnesHut: { gravitationalConstant: -2000, centralGravity: 0.15, springLength: 150 }, stabilization: { iterations: 100 } },
        interaction: { hover: true, tooltipDelay: 100 },
      })
      networkRef.current = network

      network.on('click', (params: any) => {
        if (params.nodes.length > 0) {
          const nodeId = params.nodes[0]
          if (typeof nodeId === 'string' && nodeId.startsWith('fact:')) {
            const f = facts.find((x) => x.id === nodeId.replace('fact:', ''))
            if (f) setSelected(f)
          } else {
            const b = beliefs.find((x) => x.id === nodeId)
            if (b) setSelected(b)
          }
        } else { setSelected(null) }
      })
    }
    loadVis()
    return () => { networkRef.current?.destroy() }
  }, [beliefs, edges, facts])

  const isBelief = (item: any): item is BeliefItem => 'principle' in item
  const isFact = (item: any): item is FactItem => 'predicate' in item

  return (
    <div className="px-6 py-6 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-black">Memory Graph</h1>
        <div className="flex gap-4 text-xs text-neutral-400">
          <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded-full bg-black inline-block" /> Beliefs ({beliefs.length})</span>
          <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded bg-neutral-300 inline-block" /> Facts ({facts.length})</span>
          <span className="font-mono">{edges.length} edges</span>
        </div>
      </div>

      <div className="flex gap-3" style={{ height: 'calc(100vh - 12rem)' }}>
        <div ref={containerRef} className="flex-1 bg-white rounded-lg border border-neutral-200" />
        {selected && (
          <div className="w-72 bg-white rounded-lg border border-neutral-200 p-5 overflow-y-auto">
            {isBelief(selected) && (
              <>
                <span className="text-xs px-2 py-1 rounded bg-black text-white font-mono">belief</span>
                <p className="mt-4 text-sm text-black leading-relaxed">{selected.principle}</p>
                <div className="mt-4 text-xs text-neutral-400 space-y-1 font-mono">
                  <div>id: {selected.id.slice(0, 8)}</div>
                  <div>confidence: {selected.confidence}</div>
                </div>
              </>
            )}
            {isFact(selected) && (
              <>
                <span className="text-xs px-2 py-1 rounded bg-neutral-200 text-neutral-700 font-mono">fact</span>
                <div className="mt-4 space-y-2 text-sm">
                  <div><span className="text-neutral-400">subject:</span> <span className="text-black font-medium">{selected.subject}</span> {selected.subject_type && <span className="text-xs text-neutral-400 font-mono">[{selected.subject_type}]</span>}</div>
                  <div><span className="text-neutral-400">predicate:</span> <span className="text-black font-mono font-medium">{selected.predicate}</span></div>
                  <div><span className="text-neutral-400">object:</span> <span className="text-black font-medium">{selected.object}</span> {selected.object_type && <span className="text-xs text-neutral-400 font-mono">[{selected.object_type}]</span>}</div>
                </div>
                <div className="mt-4 text-xs text-neutral-400 font-mono">confidence: {selected.confidence}</div>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
