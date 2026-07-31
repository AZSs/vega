import { useState, useEffect } from "react"
import { apiClient, type ChapterInfo } from "@/api/client"

export default function ChaptersTab({ docId }: { docId: string }) {
  const [chapters, setChapters] = useState<ChapterInfo[]>([])
  const [selected, setSelected] = useState<number | null>(null)
  const [content, setContent] = useState("")
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!docId) return
    apiClient.getChapters(docId).then(setChapters).catch(() => setChapters([]))
  }, [docId])

  useEffect(() => {
    if (!docId || selected === null) return
    setLoading(true)
    apiClient.getChapter(docId, selected).then((r) => setContent(r.content)).finally(() => setLoading(false))
  }, [docId, selected])

  if (!docId) return <p className="text-slate-400">请先选择文档</p>

  return (
    <div className="flex gap-4">
      <aside className="w-48 shrink-0 space-y-1">
        <h3 className="text-sm font-semibold text-slate-700 mb-2">章节列表</h3>
        {chapters.length === 0 ? (
          <p className="text-slate-400 text-sm">暂无章节</p>
        ) : (
          chapters.map((c) => (
            <button key={c.chapter} onClick={() => setSelected(c.chapter)}
              className={`w-full text-left px-3 py-2 rounded-md text-sm ${selected === c.chapter ? "bg-slate-900 text-white" : "hover:bg-slate-100"}`}>
              第{c.chapter}章
              <span className="text-xs opacity-60 ml-2">{c.length}字</span>
            </button>
          ))
        )}
      </aside>
      <div className="flex-1 bg-white rounded-lg border p-6 min-h-[400px]">
        {loading ? <p className="text-slate-400">加载中...</p> :
         selected === null ? <p className="text-slate-400">选择左侧章节阅读</p> :
         <div className="prose prose-sm max-w-none whitespace-pre-wrap">{content}</div>}
      </div>
    </div>
  )
}
