import { useState, useEffect, useCallback } from "react"
import { Upload, FileText, Database } from "lucide-react"
import { apiClient, uploadBook, type DocInfo } from "@/api/client"

export default function DocsTab({ selectedDoc, onSelect }: { selectedDoc: string; onSelect: (d: string) => void }) {
  const [docs, setDocs] = useState<DocInfo[]>([])
  const [file, setFile] = useState<File | null>(null)
  const [docId, setDocId] = useState("")
  const [shards, setShards] = useState(4)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState("")

  const refresh = useCallback(async () => {
    try { setDocs(await apiClient.listDocs()) } catch { /* ignore */ }
  }, [])

  useEffect(() => { refresh() }, [refresh])

  const handleUpload = async () => {
    if (!file || !docId) return
    setUploading(true); setError("")
    try {
      await uploadBook(file, docId, { shards })
      await refresh()
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
        <button onClick={handleUpload} disabled={!file || !docId || uploading}
          className="mt-4 bg-slate-900 text-white px-4 py-2 rounded-md text-sm font-medium disabled:opacity-50">
          {uploading ? "上传中..." : "开始建库"}
        </button>
        {error && <p className="mt-2 text-red-500 text-sm">{error}</p>}
      </section>

      <section>
        <h2 className="text-lg font-semibold mb-4">文档列表</h2>
        {docs.length === 0 ? (
          <p className="text-slate-400 text-sm">暂无文档，上传一本书开始</p>
        ) : (
          <div className="grid gap-3">
            {docs.map((d) => (
              <button key={d.doc_id} onClick={() => onSelect(d.doc_id)}
                className={`text-left bg-white rounded-lg border p-4 hover:border-slate-400 transition-colors ${selectedDoc === d.doc_id ? "border-slate-900" : ""}`}>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <FileText className="w-4 h-4 text-slate-400" />
                    <span className="font-medium">{d.doc_id}</span>
                  </div>
                  <div className="flex gap-4 text-sm text-slate-500">
                    {d.has_lightrag && <span className="flex items-center gap-1"><Database className="w-3.5 h-3.5" /> LightRAG</span>}
                    <span>{d.entity_count} 实体</span>
                    <span>{d.chapter_count} 章</span>
                  </div>
                </div>
              </button>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}
