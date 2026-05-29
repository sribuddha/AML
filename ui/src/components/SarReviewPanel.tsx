import { Link } from "react-router-dom"
import ReviewCard from "./ReviewCard"
import type { UseSarReviewReturn } from "../hooks/useSarReview"

const RISK_LEVELS = ["all", "high", "medium", "low"] as const
const LEVEL_STYLES: Record<string, string> = {
  all: "bg-slate-800 text-white",
  high: "bg-red-600 text-white",
  medium: "bg-amber-500 text-white",
  low: "bg-green-600 text-white",
}

interface SarReviewPanelProps {
  review: UseSarReviewReturn
  customerId?: string | null
  title?: string
  description?: string
}

export default function SarReviewPanel({ review, customerId, title, description }: SarReviewPanelProps) {
  const {
    filteredSars, loading, error, completed, reviewing, batchReviewing,
    selectedIds, setRiskLevel, toggleSelect, toggleSelectAll,
    review: handleReview, batchReview, refetch,
  } = review

  if (loading) {
    return (
      <div className="space-y-4">
        {[1, 2, 3].map((i) => (
          <div key={i} className="bg-white border border-slate-200 rounded-lg p-5 space-y-3">
            <div className="h-4 bg-slate-200 rounded w-48 animate-pulse" />
            <div className="h-4 bg-slate-200 rounded w-96 animate-pulse" />
            <div className="h-4 bg-slate-200 rounded w-64 animate-pulse" />
          </div>
        ))}
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-center justify-between">
        <span className="text-sm text-red-700">{error}</span>
        <button onClick={refetch} className="text-sm font-medium text-red-700 hover:text-red-900">
          Retry
        </button>
      </div>
    )
  }

  if (completed) {
    return (
      <div className="bg-green-50 border border-green-200 rounded-lg p-8 text-center">
        <div className="text-3xl mb-2">&#9989;</div>
        <h3 className="text-lg font-semibold text-green-800 mb-1">You are all up to date.</h3>
        {customerId && (
          <Link to="/compliance" className="mt-3 inline-block text-sm text-blue-600 hover:text-blue-800 underline">
            View all pending reviews
          </Link>
        )}
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {title && (
        <div>
          <h2 className="text-xl font-bold text-slate-800">{title}</h2>
          {description && <p className="text-sm text-slate-500 mt-0.5">{description}</p>}
        </div>
      )}

      {/* Risk filter pills */}
      <div className="flex items-center gap-2">
        {RISK_LEVELS.map((level) => (
          <button
            key={level}
            onClick={() => setRiskLevel(level)}
            className={`px-3 py-1 text-xs font-medium rounded-full transition-colors ${
              review.riskLevel === level
                ? LEVEL_STYLES[level]
                : "bg-slate-100 text-slate-600 hover:bg-slate-200"
            }`}
          >
            {level === "all" ? "All" : level.charAt(0).toUpperCase() + level.slice(1)}
          </button>
        ))}
      </div>

      {/* Select + batch actions */}
      {filteredSars.length > 0 && (
        <div className="flex items-center justify-between">
          <label className="flex items-center gap-2 text-sm text-slate-600 cursor-pointer">
            <input
              type="checkbox"
              checked={selectedIds.size > 0 && selectedIds.size === filteredSars.length}
              onChange={toggleSelectAll}
              className="rounded border-slate-300 text-blue-600 focus:ring-blue-500"
            />
            {selectedIds.size > 0 ? `${selectedIds.size} selected` : "Select all"}
          </label>
          <div className="flex gap-2">
            <button
              onClick={() => batchReview("confirmed")}
              disabled={batchReviewing || selectedIds.size === 0}
              className="px-3 py-1.5 text-xs font-medium rounded-lg bg-green-600 text-white hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {batchReviewing ? "..." : "Accept All"}
            </button>
            <button
              onClick={() => batchReview("dismissed")}
              disabled={batchReviewing || selectedIds.size === 0}
              className="px-3 py-1.5 text-xs font-medium rounded-lg border border-slate-300 text-slate-700 hover:bg-slate-100 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {batchReviewing ? "..." : "Dismiss All"}
            </button>
          </div>
        </div>
      )}

      {/* SAR cards */}
      <div className="space-y-3">
        {filteredSars.map((sar) => (
          <div key={sar.sar_id} className="flex items-start gap-3">
            <input
              type="checkbox"
              checked={selectedIds.has(sar.sar_id)}
              onChange={() => toggleSelect(sar.sar_id)}
              className="mt-5 ml-1 rounded border-slate-300 text-blue-600 focus:ring-blue-500 shrink-0"
            />
            <div className="flex-1 min-w-0">
              <ReviewCard
                sar={sar}
                onReview={(action) => handleReview(sar.sar_id, action)}
                reviewing={reviewing === sar.sar_id}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
