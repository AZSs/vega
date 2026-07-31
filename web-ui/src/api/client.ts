const BASE = ""

export async function api<T>(path: string, opts?: RequestInit): Promise<T> {
  const resp = await fetch(`${BASE}${path}`, {
    ...opts,
    headers: { "Content-Type": "application/json", ...opts?.headers },
  })
  if (!resp.ok) {
    const text = await resp.text()
    throw new Error(`${resp.status}: ${text}`)
  }
  return resp.json()
}

export async function uploadBook(file: File, docId: string, opts: { shards?: number; plugin?: string }) {
  const form = new FormData()
  form.append("file", file)
  form.append("doc_id", docId)
  if (opts.shards) form.append("shards", String(opts.shards))
  if (opts.plugin) form.append("plugin", opts.plugin)
  const resp = await fetch(`${BASE}/api/upload`, { method: "POST", body: form })
  return resp.json()
}

export interface DocInfo {
  doc_id: string
  has_lightrag: boolean
  entity_count: number
  chapter_count: number
}

export interface EntityInfo {
  name: string
  type: string
  description: string
  source_id: string
}

export interface Profile {
  name: string
  race?: string | null
  origin?: string | null
  age?: string | number | null
  dao_fruit?: string | { name: string; status?: string } | null
  gender?: string | null
  personality?: string | null
  appearance?: { desc: string }[]
  relations?: { target: string; type?: string }[]
  immortalization_path?: string | null
  _source_chunks?: number
  _facts?: number
  key_events?: { seg: number; desc: string }[]
}

export interface ChapterInfo {
  chapter: number
  title: string
  length: number
}

export const apiClient = {
  listDocs: () => api<DocInfo[]>("/api/docs"),
  getEntities: (docId: string) => api<EntityInfo[]>(`/api/docs/${docId}/entities`),
  getProfile: (docId: string, entity: string, aliases: string[]) =>
    api<Profile>(`/api/docs/${docId}/profile?entity=${encodeURIComponent(entity)}&aliases=${encodeURIComponent(aliases.join(","))}`),
  getChapters: (docId: string) => api<ChapterInfo[]>(`/api/docs/${docId}/chapters`),
  getChapter: (docId: string, n: number) => api<{ content: string }>(`/api/docs/${docId}/chapters/${n}`),
  triggerWrite: (docId: string, opts: { entity: string; aliases: string[]; chapters: number; premise: string }) =>
    api<{ task_id: string }>(`/api/docs/${docId}/write`, {
      method: "POST",
      body: JSON.stringify(opts),
    }),
}
