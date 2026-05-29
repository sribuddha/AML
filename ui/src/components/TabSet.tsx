import { cn } from "../lib/cn"

export interface Tab {
  id: string
  label: string
}

interface TabSetProps {
  tabs: Tab[]
  active: string
  onChange: (id: string) => void
}

export default function TabSet({ tabs, active, onChange }: TabSetProps) {
  return (
    <div className="flex gap-1 bg-slate-100 rounded-lg p-1 w-fit">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          onClick={() => onChange(tab.id)}
          className={cn(
            "px-4 py-2 text-sm font-medium rounded-md transition-colors",
            active === tab.id
              ? "bg-white text-slate-800 shadow-sm"
              : "text-slate-500 hover:text-slate-700",
          )}
        >
          {tab.label}
        </button>
      ))}
    </div>
  )
}
