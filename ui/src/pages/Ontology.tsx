import { useEffect, useState, useCallback } from 'react'
import { api, type ContextInfo } from '../api'

export default function Ontology() {
  const [ctx, setCtx] = useState<ContextInfo | null>(null)
  const [uploading, setUploading] = useState(false)
  const [dragOver, setDragOver] = useState(false)
  const [uploadResult, setUploadResult] = useState<{ filename: string; types: string[]; predicates: string[] } | null>(null)

  useEffect(() => { api.context().then(setCtx) }, [])

  const handleUpload = async (file: File) => {
    setUploading(true)
    setUploadResult(null)
    try {
      const result = await api.uploadContext(file)
      setUploadResult({ filename: result.filename, types: result.types, predicates: result.predicates })
      api.context().then(setCtx)
    } catch (e: any) {
      alert(`Upload failed: ${e.message}`)
    } finally {
      setUploading(false)
    }
  }

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    const file = e.dataTransfer.files[0]
    if (file) handleUpload(file)
  }, [])

  const onFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) handleUpload(file)
  }

  return (
    <div className="space-y-5">
      <h1 className="text-xl font-semibold text-zinc-900">Ontology</h1>

      <div
        onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
        className={`border-2 border-dashed rounded-xl p-8 text-center transition-colors ${
          dragOver ? 'border-indigo-400 bg-indigo-50/50' : 'border-zinc-200 bg-white'
        }`}
      >
        <p className="text-xs text-zinc-400 mb-3">
          {uploading ? 'Uploading...' : 'Drag and drop a .ttl or .jsonld file here'}
        </p>
        <label className="px-4 py-2 bg-indigo-500 text-white text-xs rounded-lg hover:bg-indigo-600 cursor-pointer transition-colors">
          Choose file
          <input type="file" accept=".ttl,.jsonld" onChange={onFileSelect} className="hidden" />
        </label>
      </div>

      {uploadResult && (
        <div className="bg-emerald-50 border border-emerald-100 rounded-xl p-4 text-xs text-emerald-700">
          Loaded <span className="font-medium">{uploadResult.filename}</span>: {uploadResult.types.length} types, {uploadResult.predicates.length} predicates
        </div>
      )}

      {ctx?.loaded && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="bg-white rounded-xl border border-zinc-100 shadow-sm p-5">
            <h2 className="text-xs font-medium text-zinc-900 mb-3">Types ({ctx.type_count})</h2>
            <div className="flex flex-wrap gap-1.5">
              {ctx.types.map((t) => (
                <span key={t} className="px-2 py-1 bg-violet-50 text-violet-600 text-[10px] rounded-md border border-violet-100">
                  {t}
                </span>
              ))}
            </div>
          </div>

          <div className="bg-white rounded-xl border border-zinc-100 shadow-sm p-5">
            <h2 className="text-xs font-medium text-zinc-900 mb-3">Predicates ({ctx.predicate_count})</h2>
            <div className="flex flex-wrap gap-1.5">
              {ctx.predicates.map((p) => (
                <span key={p} className="px-2 py-1 bg-blue-50 text-blue-600 text-[10px] rounded-md border border-blue-100">
                  {p}
                </span>
              ))}
            </div>
          </div>
        </div>
      )}

      {ctx && !ctx.loaded && (
        <div className="text-center py-8 text-zinc-400 text-xs">
          No ontology loaded. Upload a Turtle (.ttl) or JSON-LD (.jsonld) file to get started.
        </div>
      )}
    </div>
  )
}
