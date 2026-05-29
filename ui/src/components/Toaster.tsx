import { useState, useEffect } from "react"
import { cn } from "../lib/cn"
import { subscribe, dismiss, type Toast } from "../lib/toast"

const VARIANT_STYLES: Record<string, string> = {
  success: "bg-green-600 text-white",
  error: "bg-red-600 text-white",
  info: "bg-slate-800 text-white",
  warning: "bg-amber-500 text-white",
}

function ToastItem({ toast: t }: { toast: Toast }) {
  return (
    <div
      className={cn(
        "flex items-center gap-2 px-4 py-3 rounded-lg shadow-lg text-sm font-medium animate-in slide-in-from-right",
        "min-w-[280px] max-w-sm",
        VARIANT_STYLES[t.variant],
      )}
    >
      <span className="flex-1">{t.message}</span>
      <button
        onClick={() => dismiss(t.id)}
        className="shrink-0 opacity-70 hover:opacity-100 leading-none text-lg"
      >
        &times;
      </button>
    </div>
  )
}

export default function Toaster() {
  const [items, setItems] = useState<Toast[]>([])

  useEffect(() => {
    return subscribe((toasts) => setItems([...toasts]))
  }, [])

  if (items.length === 0) return null

  return (
    <div className="fixed bottom-4 right-4 z-[100] flex flex-col gap-2 items-end pointer-events-none">
      {items.map((t) => (
        <div key={t.id} className="pointer-events-auto">
          <ToastItem toast={t} />
        </div>
      ))}
    </div>
  )
}
