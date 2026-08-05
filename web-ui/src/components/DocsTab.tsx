import { useState, useEffect, useCallback, useRef } from "react"
import { Upload, FileText, Database, Loader2, CheckCircle } from "lucide-react"
import { apiClient, uploadBook, type DocInfo } from "@/api/client"

interface IngestStatus {
  status: string
  graph_nodes: number
  message: string
}

export default function DocsTab({ selectedDoc, onSelect }: { selectedDoc: string; onSelect: (d: string) => void }) {
  const [docs, setDocs] = useState<DocInfo[]>([])
  const [file, setFile] = useState<File | null>(null)
  const [docId, setDocId] = useState("")
  const [shards, setShards] = useState(4)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState("")
  const [ingestingDoc, setIngestingDoc] = useState<string>("")
  const [ingestStatus, setIngestStatus] = useState<IngestStatus | null>(null)
  const eventSourceRef = useRef<EventSource | null>(null)

  const refresh = useCallback(async () => {
    try { setDocs(await apiClient.listDocs()) } catch { /* ignore */ }
  }, [])

  useEffect(() => { refresh() }, [refresh])

  // SSE 接收 ingest 进度
  const startSSE = (id: string) => {
    setIngestingDoc(id)
    if (eventSourceRef.current) eventSourceRef.current.close()
    const es = new EventSource(`/api/docs/${id}/ingest-stream`)
    eventSourceRef.current = es
    es.onmessage = (e) => {
      try {
        const data: IngestStatus = JSON.parse(e.data)
        setIngestStatus(data)
        refresh()
        if (data.status === "done" || data.status === "failed") {
          es.close()
          setIngestingDoc("")
          setIngestStatus(null)
        }
      } catch { /* ignore */ }
    }
    es.onerror = () => {
      es.close()
      setIngestingDoc("")
      setIngestStatus(null)
    }
  }

  useEffect(() => () => { eventSourceRef.current?.close() }, [])

  const handleUpload = async () => {
    if (!file || !docId) return
    setUploading(true); setError("")
    try {
      await uploadBook(file, docId, { shards })
      await refresh()
      startSSE(docId)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally { setUploading(false) }
  }

  return (
    <div className="space-y-6">
      <section className="bg-white rounded-lg border p-6">
        <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <Upload className="w-5 h-5" /> 上传书籍
        </h2>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm text-slate-600 mb-1">文档 ID</label>
            <input value={docId} onChange={(e) => setDocId(e.target.value)}
              placeholder="如 shuixian" className="w-full border rounded-md px-3 py-2 text-sm" />
          </div>
          <div>
            <label className="block text-sm text-slate-600 mb-1">并行分片数</label>
            <input type="number" value={shards} onChange={(e) => setShards(Number(e.target.value))}
              className="w-full border rounded-md px-3 py-2 text-sm" />
          </div>
        </div>
        <div className="mt-4">
          <label className="block text-sm text-slate-600 mb-1">选择 .txt 文件</label>
          <input type="file" accept=".txt" onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            className="text-sm" />
        </div>
        <button onClick={handleUpload} disabled={!file || !docId || uploading || !!ingestingDoc}
          className="mt-4 bg-slate-900 text-white px-4 py-2 rounded-md text-sm font-medium disabled:opacity-50">
          {uploading ? "上传中..." : ingestingDoc ? "建库中..." : "开始建库"}
        </button>
        {error && <p className="mt-2 text-red-500 text-sm">{error}</p>}
      </section>

      {/* ingest 进度条(SSE 实时) */}
      {ingestingDoc && ingestStatus && (
        <section className="bg-blue-50 rounded-lg border border-blue-200 p-4 flex items-center gap-3">
          <Loader2 className="w-5 h-5 text-blue-500 animate-spin" />
          <div className="flex-1">
            <p className="text-sm font-medium text-blue-900">
              正在建库：{ingestingDoc}
            </p>
            <p className="text-xs text-blue-600">
              {ingestStatus.message || `已有 ${ingestStatus.graph_nodes} 实体...`}
            </p>
          </div>
          {ingestStatus.graph_nodes > 0 && (
            <span className="text-2xl font-bold text-blue-600">{ingestStatus.graph_nodes}</span>
          )}
        </section>
      )}

      <section>
        <h2 className="text-lg font-semibold mb-4">文档列表</h2>
        {docs.length === 0 ? (
          <p className="text-slate-400 text-sm">暂无文档，上传一本书开始</p>
        ) : (
          <div className="grid gap-3">
            {docs.map((d) => {
              const isIngesting = ingestingDoc === d.doc_id
              return (
                <button key={d.doc_id} onClick={() => onSelect(d.doc_id)} disabled={isIngesting}
                  className={`text-left bg-white rounded-lg border p-4 transition-colors ${
                    isIngesting ? "border-blue-300 opacity-70 cursor-wait" :
                    selectedDoc === d.doc_id ? "border-slate-900" : "hover:border-slate-400"
                  }`}>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      {isIngesting
                        ? <Loader2 className="w-4 h-4 text-blue-500 animate-spin" />
                        : d.entity_count > 0
                        ? <CheckCircle className="w-4 h-4 text-green-500" />
                        : <FileText className="w-4 h-4 text-slate-400" />}
                      <span className="font-medium">{d.doc_id}</span>
                    </div>
                    <div className="flex gap-4 text-sm text-slate-500">
                      {d.has_lightrag && <span className="flex items-center gap-1"><Database className="w-3.5 h-3.5" /> LightRAG</span>}
                      <span className={isIngesting && ingestStatus?.graph_nodes ? "text-blue-600 font-medium" : ""}>
                        {isIngesting && ingestStatus?.graph_nodes
                          ? `${ingestStatus.graph_nodes} 实体(增长中)`
                          : `${d.entity_count} 实体`}
                      </span>
                      <span>{d.chapter_count} 章</span>
                    </div>
                  </div>
                </button>
              )
            })}
          </div>
        )}
      </section>
    </div>
  )
}
