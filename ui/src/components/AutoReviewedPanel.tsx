import { useState, useEffect } from "react"
import { api } from "../api/client"
import type { AutoReviewedItem, PaginatedResponse } from "../types"

interface AutoReviewedPanelProps {
  uploadId: string | null
}

export default function AutoReviewedPanel({ uploadId }: AutoReviewedPanelProps) {
  const [items, setItems] = useState<AutoReviewedItem[]>([])
  const [loading, setLoading] = useState(false)
  const [expanded, setExpanded] = useState<string | null>(null)

  useEffect(() => {
    if (!uploadId) return
    setLoading(true)
    api
      .get<PaginatedResponse<AutoReviewedItem>>(
        `/api/uploads/${uploadId}/validation?risk_level=auto_reviewed&per_page=100`,
      )
      .then((res) => setItems(res.items))
      .catch(() => setItems([]))
      .finally(() => setLoading(false))
  }, [uploadId])

  if (!uploadId) {
    return (
      <p className="text-sm text-slate-500 py-4">
        Select an upload to view auto-reviewed transactions.
      </p>
    )
  }

  if (loading) {
    return (
      <div className="space-y-3 py-4">
        {[1, 2].map((i) => (
          <div key={i} className="h-16 bg-slate-100 rounded-lg animate-pulse" />
        ))}
      </div>
    )
  }

  if (items.length === 0) {
    return (
      <p className="text-sm text-slate-500 py-4">
        No auto-reviewed transactions for this upload.
      </p>
    )
  }

  return (
    <div className="space-y-2 py-4">
      <p className="text-xs text-slate-400 mb-2">
        {items.length} transaction{items.length !== 1 ? "s" : ""} cleared by LLM triage
      </p>
      {items.map((item) => (
        <div
          key={item.source_txn_id}
          className="bg-white border border-slate-200 rounded-lg overflow-hidden"
        >
          <button
            onClick={() =>
              setExpanded(expanded === item.source_txn_id ? null : item.source_txn_id)
            }
            className="w-full px-4 py-3 flex items-center justify-between text-left hover:bg-slate-50 transition-colors"
          >
            <div className="flex items-center gap-3 min-w-0">
              <span className="text-xs font-mono text-slate-500 shrink-0">
                {item.source_txn_id}
              </span>
              <span className="text-sm font-medium text-slate-800 truncate">
                {item.counterparty || "N/A"}
              </span>
              <span className="text-sm text-slate-600 shrink-0">
                ${item.amount?.toLocaleString() ?? "N/A"}
              </span>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <span className="inline-flex items-center px-2 py-0.5 text-xs font-medium rounded-full bg-green-100 text-green-700">
                auto-reviewed
              </span>
              <span className="text-slate-400 text-xs">
                {expanded === item.source_txn_id ? "▲" : "▼"}
              </span>
            </div>
          </button>
          {expanded === item.source_txn_id && (
            <div className="px-4 pb-3 border-t border-slate-100 pt-2 space-y-2">
              {item.flag_details && Object.keys(item.flag_details).length > 0 && (
                <div>
                  <span className="text-xs font-medium text-slate-500">Triggered rules:</span>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {Object.values(item.flag_details).map((name) => (
                      <span
                        key={name}
                        className="inline-flex items-center px-2 py-0.5 text-xs rounded-full bg-amber-50 text-amber-700"
                      >
                        {name}
                      </span>
                    ))}
                  </div>
                </div>
              )}
              {item.triage_reasoning && (
                <div>
                  <span className="text-xs font-medium text-slate-500">LLM reasoning:</span>
                  <p className="text-xs text-slate-600 mt-0.5 whitespace-pre-wrap">
                    {item.triage_reasoning}
                  </p>
                </div>
              )}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
