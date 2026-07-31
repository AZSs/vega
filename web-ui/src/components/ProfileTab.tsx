import { useState } from "react"
import { apiClient, type Profile } from "@/api/client"

export default function ProfileTab({ docId, entity }: { docId: string; entity: string }) {
  const [aliases, setAliases] = useState("")
  const [profile, setProfile] = useState<Profile | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")

  const fetchProfile = async () => {
    if (!docId || !entity) return
    setLoading(true); setError("")
    try {
      const aliasList = aliases.split(",").map((a) => a.trim()).filter(Boolean)
      const p = await apiClient.getProfile(docId, entity, aliasList)
      setProfile(p)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally { setLoading(false) }
  }

  if (!docId || !entity) return <p className="text-slate-400">请先选择文档和实体</p>

  const fields: { key: keyof Profile; label: string }[] = [
    { key: "race", label: "种族" }, { key: "gender", label: "性别" }, { key: "age", label: "年龄" },
    { key: "origin", label: "身世" }, { key: "personality", label: "性格" }, { key: "immortalization_path", label: "成仙路径" },
  ]

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <input value={entity} readOnly className="border rounded-md px-3 py-2 text-sm bg-slate-50" />
        <input value={aliases} onChange={(e) => setAliases(e.target.value)} placeholder="别名(逗号分隔)"
          className="flex-1 border rounded-md px-3 py-2 text-sm" />
        <button onClick={fetchProfile} disabled={loading}
          className="bg-slate-900 text-white px-4 py-2 rounded-md text-sm font-medium disabled:opacity-50">
          {loading ? "生成中..." : "生成画像"}
        </button>
      </div>
      {error && <p className="text-red-500 text-sm">{error}</p>}

      {profile && (
        <div className="bg-white rounded-lg border p-6 space-y-4">
          <h2 className="text-xl font-bold">{profile.name}</h2>
          {profile._source_chunks && (
            <p className="text-xs text-slate-400">基于 {profile._source_chunks} 个原文片段溯源 · {profile._facts ?? 0} 条事实</p>
          )}
          <div className="grid grid-cols-2 gap-3">
            {fields.map((f) => {
              const v = profile[f.key]
              if (!v) return null
              return (
                <div key={f.key} className="border rounded-md p-3">
                  <dt className="text-xs text-slate-500">{f.label}</dt>
                  <dd className="text-sm font-medium mt-1">{String(v)}</dd>
                </div>
              )
            })}
            {profile.dao_fruit && (
              <div className="border rounded-md p-3">
                <dt className="text-xs text-slate-500">道果</dt>
                <dd className="text-sm font-medium mt-1">
                  {typeof profile.dao_fruit === "string"
                    ? profile.dao_fruit
                    : `${profile.dao_fruit.name}(${profile.dao_fruit.status ?? ""})`}
                </dd>
              </div>
            )}
          </div>
          {profile.relations?.length ? (
            <div>
              <h3 className="text-sm font-semibold text-slate-700 mb-2">关系网</h3>
              <div className="flex flex-wrap gap-2">
                {profile.relations.map((r, i) => (
                  <span key={i} className="text-xs px-2 py-1 rounded bg-slate-100">
                    {r.target}{r.type ? `(${r.type})` : ""}
                  </span>
                ))}
              </div>
            </div>
          ) : null}
          {profile.key_events?.length ? (
            <div>
              <h3 className="text-sm font-semibold text-slate-700 mb-2">关键事件</h3>
              <ul className="space-y-1">
                {profile.key_events.slice(0, 10).map((e, i) => (
                  <li key={i} className="text-sm text-slate-600">· {e.desc}</li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      )}
    </div>
  )
}
