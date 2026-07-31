import { useState, useEffect } from "react"
import { Search } from "lucide-react"
import { apiClient, type EntityInfo } from "@/api/client"

export default function EntitiesTab({ docId, onSelectEntity }: { docId: string; onSelectEntity: (e: string) => void }) {
  const [entities, setEntities] = useState<EntityInfo[]>([])
  const [search, setSearch] = useState("")
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!docId) return
    setLoading(true)
    apiClient.getEntities(docId).then(setEntities).catch(() => setEntities([])).finally(() => setLoading(false))
  }, [docId])

  const filtered = entities.filter((e) =>
    !search || e.name.includes(search) || e.type.includes(search) || e.description.includes(search)
  )

  if (!docId) return <p className="text-slate-400">请先在「书籍管理」选择文档</p>

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-2.5 w-4 h-4 text-slate-400" />
          <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="搜索实体名/类型/描述..."
            className="w-full border rounded-md pl-9 pr-3 py-2 text-sm" />
        </div>
        <span className="text-sm text-slate-500">{filtered.length} / {entities.length}</span>
      </div>

      {loading && <p className="text-slate-400">加载中...</p>}

      <div className="grid gap-2">
        {filtered.slice(0, 100).map((e, i) => (
          <button key={i} onClick={() => onSelectEntity(e.name)}
            className="text-left bg-white rounded-lg border p-3 hover:border-slate-400">
            <div className="flex items-center gap-2">
              <span className="font-medium text-sm">{e.name}</span>
              <span className="text-xs px-1.5 py-0.5 rounded bg-slate-100 text-slate-600">{e.type}</span>
            </div>
            {e.description && (
              <p className="text-sm text-slate-500 mt-1 line-clamp-2">{e.description.slice(0, 120)}</p>
            )}
          </button>
        ))}
        {filtered.length > 100 && <p className="text-center text-slate-400 text-sm">仅显示前 100 条，缩小搜索范围...</p>}
      </div>
    </div>
  )
}
