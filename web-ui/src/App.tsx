import { useState } from "react"
import { BookOpen, Users, UserCircle, PenTool, BookText } from "lucide-react"
import { cn } from "@/lib/utils"
import DocsTab from "@/components/DocsTab"
import EntitiesTab from "@/components/EntitiesTab"
import ProfileTab from "@/components/ProfileTab"
import WriteTab from "@/components/WriteTab"
import ChaptersTab from "@/components/ChaptersTab"

type Tab = "docs" | "entities" | "profile" | "write" | "chapters"

const TABS: { id: Tab; label: string; icon: React.ComponentType<{ className?: string }> }[] = [
  { id: "docs", label: "书籍管理", icon: BookOpen },
  { id: "entities", label: "实体发现", icon: Users },
  { id: "profile", label: "角色画像", icon: UserCircle },
  { id: "write", label: "同人写作", icon: PenTool },
  { id: "chapters", label: "章节阅读", icon: BookText },
]

export default function App() {
  const [tab, setTab] = useState<Tab>("docs")
  const [selectedDoc, setSelectedDoc] = useState<string>("")
  const [selectedEntity, setSelectedEntity] = useState<string>("")

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b bg-white px-6 py-3 flex items-center gap-6">
        <h1 className="text-lg font-bold text-slate-900">Vega</h1>
        <span className="text-xs text-slate-400">长文本知识引擎</span>
        <nav className="flex gap-1 ml-auto">
          {TABS.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={cn(
                "flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-colors",
                tab === t.id ? "bg-slate-900 text-white" : "text-slate-600 hover:bg-slate-100"
              )}
            >
              <t.icon className="w-4 h-4" />
              {t.label}
            </button>
          ))}
        </nav>
      </header>

      <main className="max-w-6xl mx-auto p-6">
        {tab === "docs" && (
          <DocsTab
            selectedDoc={selectedDoc}
            onSelect={(d) => { setSelectedDoc(d); setTab("entities") }}
          />
        )}
        {tab === "entities" && (
          <EntitiesTab
            docId={selectedDoc}
            onSelectEntity={(e) => { setSelectedEntity(e); setTab("profile") }}
          />
        )}
        {tab === "profile" && <ProfileTab docId={selectedDoc} entity={selectedEntity} />}
        {tab === "write" && <WriteTab docId={selectedDoc} />}
        {tab === "chapters" && <ChaptersTab docId={selectedDoc} />}
      </main>
    </div>
  )
}
