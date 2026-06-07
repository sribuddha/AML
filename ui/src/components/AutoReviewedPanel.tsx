import { useState, useEffect } from "react"
import { api } from "../api/client"
import type { AutoReviewedItem, PaginatedResponse, UploadSummary } from "../types"

interface AutoReviewedPanelProps {
  uploadId: string | null
  onSelectUpload: (uploadId: string | null) => void
}

export default function AutoReviewedPanel({ uploadId, onSelectUpload }: AutoReviewedPanelProps) {
  const [items, setItems] = useState<AutoReviewedItem[]>([])
  const [loading, setLoading] = useState(false)
  const [expanded, setExpanded] = useState<string | null>(null)
  const [uploads, setUploads] = useState<UploadSummary[]>([])
  const [uploadsLoading, setUploadsLoading] = useState(false)

  useEffect(() => {
    if (!uploadId) {
      setUploadsLoading(true)
      api
        .get<PaginatedResponse<UploadSummary>>("/api/uploads/search?per_page=100")
        .then((res) => setUploads(res.items))
        .catch(() => setUploads([]))
        .finally(() => setUploadsLoading(false))
      return
    }
    setLoading(true)
    api
      .get<PaginatedResponse<AutoReviewedItem>>(
        `/api/uploads/${uploadId}/validation?risk_level=auto_reviewed&per_page=100`,
      )
      .then((res) => setItems(res.items))
      .catch(() => setItems([]))
      .finally(() => setLoading(false))
  }, [uploadId])

  const upload = uploads.find((u) => u.id === uploadId)
  const label = upload ? `${upload.filename} (${upload.id.slice(0, 8)})` : uploadId

  return (
    <div className="bg-white border border-slate-200 rounded-lg overflow-hidden">
      {/* Section 1: Header / Controls */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100 bg-slate-50/50">
        <div className="flex items-center gap-3 min-w-0">
          {uploadId ? (
            <button
              onClick={() => onSelectUpload(null)}
              className="text-xs font-medium text-blue-600 hover:text-blue-800 shrink-0"
            >
              &larr; Back
            </button>
          ) : (
            <span className="text-sm font-medium text-slate-700">Select an upload</span>
          )}
          {uploadId && (
            <span className="text-sm font-medium text-slate-800 truncate">{label}</span>
          )}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {!uploadId && uploadsLoading && (
            <div className="h-5 w-20 bg-slate-200 rounded animate-pulse" />
          )}
          {uploadId && items.length > 0 && (
            <span className="text-xs text-slate-500">{items.length} auto-reviewed</span>
          )}
        </div>
      </div>

      {/* Section 2: Content */}
      <div className="px-4 py-3">
        {!uploadId ? (
          uploadsLoading ? (
            <div className="h-10 bg-slate-100 rounded-lg animate-pulse" />
          ) : uploads.length === 0 ? (
            <p className="text-sm text-slate-500">No uploads found.</p>
          ) : (
            <select
              value=""
              onChange={(e) => { if (e.target.value) onSelectUpload(e.target.value) }}
              className="block w-full max-w-sm px-3 py-2 text-sm border border-slate-300 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            >
              <option value="">Choose an upload...</option>
              {uploads.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.filename} ({u.id.slice(0, 8)})
                </option>
              ))}
            </select>
          )
        ) : loading ? (
          <div className="space-y-3">
            {[1, 2].map((i) => (
              <div key={i} className="h-16 bg-slate-100 rounded-lg animate-pulse" />
            ))}
          </div>
        ) : items.length === 0 ? (
          <p className="text-sm text-slate-500">No auto-reviewed transactions for this upload.</p>
        ) : (
          <div className="space-y-2">
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
        )}
      </div>
    </div>
  )
}
