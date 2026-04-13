import { useEffect, useState, useCallback } from 'react'
import { api, type ContextInfo } from '../api'

export default function Ontology() {
  const [ctx, setCtx] = useState<ContextInfo | null>(null)
  const [uploading, setUploading] = useState(false)
  const [dragOver, setDragOver] = useState(false)
  const [uploadResult, setUploadResult] = useState<{ filename: string; types: string[]; predicates: string[] } | null>(null)

  useEffect(() => { api.context().then(setCtx) }, [])

  const handleUpload = async (file: File) => {
    setUploading(true); setUploadResult(null)
    try {
      const result = await api.uploadContext(file)
      setUploadResult({ filename: result.filename, types: result.types, predicates: result.predicates })
      api.context().then(setCtx)
    } catch (e: any) { alert(`Upload failed: ${e.message}`) }
    finally { setUploading(false) }
  }

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault(); setDragOver(false)
    const file = e.dataTransfer.files[0]
    if (file) handleUpload(file)
  }, [])

  return (
    <div className="px-6 py-8 space-y-6">
      <h1 className="text-2xl font-bold text-black">Ontology</h1>

      <div
        onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
        className={`border-2 border-dashed rounded-lg p-10 text-center transition-colors ${
          dragOver ? 'border-black bg-neutral-50' : 'border-neutral-200 bg-white'
        }`}
      >
        <p className="text-sm text-neutral-400 mb-4">
          {uploading ? 'Uploading...' : 'Drag and drop a .ttl or .jsonld file here'}
        </p>
        <label className="px-5 py-2.5 bg-black text-white text-sm font-medium rounded-lg hover:bg-neutral-800 cursor-pointer transition-colors">
          Choose file
          <input type="file" accept=".ttl,.jsonld" onChange={(e) => { const f = e.target.files?.[0]; if (f) handleUpload(f) }} className="hidden" />
        </label>
      </div>

      {uploadResult && (
        <div className="bg-white border border-neutral-200 rounded-lg p-4 text-sm text-black">
          Loaded <span className="font-mono font-medium">{uploadResult.filename}</span>: {uploadResult.types.length} types, {uploadResult.predicates.length} predicates
        </div>
      )}

      {ctx?.loaded && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="bg-white border border-neutral-200 rounded-lg p-5">
            <h2 className="text-sm font-semibold text-black mb-3">Types ({ctx.type_count})</h2>
            <div className="flex flex-wrap gap-1.5">
              {ctx.types.map((t) => (
                <span key={t} className="px-2.5 py-1 bg-neutral-100 text-neutral-700 text-xs rounded font-mono border border-neutral-200">{t}</span>
              ))}
            </div>
          </div>
          <div className="bg-white border border-neutral-200 rounded-lg p-5">
            <h2 className="text-sm font-semibold text-black mb-3">Predicates ({ctx.predicate_count})</h2>
            <div className="flex flex-wrap gap-1.5">
              {ctx.predicates.map((p) => (
                <span key={p} className="px-2.5 py-1 bg-black text-white text-xs rounded font-mono">{p}</span>
              ))}
            </div>
          </div>
        </div>
      )}

      {ctx && !ctx.loaded && (
        <div className="text-center py-10 text-neutral-400 text-sm">No ontology loaded. Upload a Turtle (.ttl) or JSON-LD (.jsonld) file to get started.</div>
      )}
    </div>
  )
}
