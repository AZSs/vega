import { useState, useRef } from "react"
import { apiClient } from "@/api/client"

export default function WriteTab({ docId }: { docId: string }) {
  const [entity, setEntity] = useState("")
  const [aliases, setAliases] = useState("")
  const [chapters, setChapters] = useState(3)
  const [premise, setPremise] = useState("")
  const [writing, setWriting] = useState(false)
  const [logs, setLogs] = useState<string[]>([])
  const [taskId, setTaskId] = useState("")
  const logRef = useRef<HTMLDivElement>(null)

  if (!docId) return <p className="text-slate-400">请先选择文档</p>

  const handleWrite = async () => {
    if (!entity) return
    setWriting(true); setLogs([])
    try {
      const result = await apiClient.triggerWrite(docId, {
        entity, aliases: aliases.split(",").map((a) => a.trim()).filter(Boolean),
        chapters, premise,
      })
      setTaskId(result.task_id)

      // SSE 流式接收 spica 日志
      const resp = await fetch(`/api/write/${result.task_id}`)
      const reader = resp.body?.getReader()
      const decoder = new TextDecoder()
      if (reader) {
        while (true) {
          const { done, value } = await reader.read()
          if (done) break
          const text = decoder.decode(value)
          text.split("\n").filter(Boolean).forEach((line) => {
            if (line.startsWith("data: ")) {
              setLogs((prev) => [...prev, line.slice(6)])
              logRef.current?.scrollTo(0, logRef.current.scrollHeight)
            }
          })
        }
      }
    } catch (e) {
      setLogs((prev) => [...prev, `错误: ${e instanceof Error ? e.message : String(e)}`])
    } finally { setWriting(false) }
  }

  return (
    <div className="space-y-4">
      <div className="bg-white rounded-lg border p-6 space-y-4">
        <h2 className="text-lg font-semibold">同人写作</h2>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm text-slate-600 mb-1">角色名</label>
            <input value={entity} onChange={(e) => setEntity(e.target.value)} placeholder="如 黄豆豆"
              className="w-full border rounded-md px-3 py-2 text-sm" />
          </div>
          <div>
            <label className="block text-sm text-slate-600 mb-1">别名</label>
            <input value={aliases} onChange={(e) => setAliases(e.target.value)} placeholder="如 不朽仙子,灰豆豆"
              className="w-full border rounded-md px-3 py-2 text-sm" />
          </div>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm text-slate-600 mb-1">章节数</label>
            <input type="number" value={chapters} onChange={(e) => setChapters(Number(e.target.value))}
              className="w-full border rounded-md px-3 py-2 text-sm" />
          </div>
        </div>
        <div>
          <label className="block text-sm text-slate-600 mb-1">故事灵感(premise)</label>
          <textarea value={premise} onChange={(e) => setPremise(e.target.value)} rows={3}
            placeholder="上古洪荒之时，有一女名黄豆豆..." className="w-full border rounded-md px-3 py-2 text-sm" />
        </div>
        <button onClick={handleWrite} disabled={!entity || writing}
          className="bg-slate-900 text-white px-4 py-2 rounded-md text-sm font-medium disabled:opacity-50">
          {writing ? "写作中..." : "开始写作"}
        </button>
      </div>

      {logs.length > 0 && (
        <div className="bg-slate-900 rounded-lg p-4">
          <div ref={logRef} className="max-h-96 overflow-y-auto font-mono text-xs text-green-400 space-y-0.5">
            {logs.map((l, i) => <div key={i}>{l}</div>)}
          </div>
        </div>
      )}
    </div>
  )
}
