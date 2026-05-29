import { useState } from "react"
import { Link, useSearchParams } from "react-router-dom"
import { useSarReview } from "../hooks/useSarReview"
import SarReviewPanel from "../components/SarReviewPanel"
import PageShell from "../components/PageShell"

export default function CompliancePage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const uploadId = searchParams.get("upload_id")
  const customerUrlId = searchParams.get("customer_id") || ""
  const [customerInput, setCustomerInput] = useState(customerUrlId)

  const review = useSarReview({
    uploadId,
    customerId: customerUrlId || undefined,
  })

  const customerDisplayName = review.customerName || customerUrlId

  return (
    <PageShell
      title="Compliance"
      description={
        <>
          {uploadId ? `Upload: ${uploadId}` : "All pending reviews"}
          {customerUrlId && !uploadId && (
            <span className="inline-flex items-center gap-1 ml-2 px-2 py-0.5 bg-blue-50 text-blue-700 rounded-full text-xs font-medium">
              {customerDisplayName}
              <button
                onClick={() => {
                  setCustomerInput("")
                  setSearchParams((prev) => { prev.delete("customer_id"); return prev })
                }}
                className="hover:text-blue-900 leading-none"
              >
                &times;
              </button>
            </span>
          )}
        </>
      }
      actions={
        !review.loading && review.sars.length > 0 ? (
          <span className="text-sm text-slate-500">
            {review.sars.length} pending{review.riskLevel !== "all" ? ` (${review.filteredSars.length} ${review.riskLevel})` : ""}
          </span>
        ) : undefined
      }
    >
      {/* Customer filter */}
      <div className="flex items-center gap-2">
        <input
          type="text"
          value={customerInput}
          onChange={(e) => setCustomerInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              setSearchParams((prev) => { prev.set("customer_id", customerInput); return prev })
            }
          }}
          placeholder="Filter by customer ID..."
          className="flex-1 max-w-xs px-3 py-1.5 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        />
        <button
          onClick={() => setSearchParams((prev) => { prev.set("customer_id", customerInput); return prev })}
          className="px-3 py-1.5 text-xs font-medium rounded-lg bg-blue-600 text-white hover:bg-blue-700 transition-colors"
        >
          Filter
        </button>
        {customerUrlId && (
          <button
            onClick={() => { setCustomerInput(""); setSearchParams((prev) => { prev.delete("customer_id"); return prev }) }}
            className="px-3 py-1.5 text-xs font-medium rounded-lg border border-slate-300 text-slate-600 hover:bg-slate-100 transition-colors"
          >
            Clear
          </button>
        )}
        {!customerUrlId && !uploadId && (
          <Link
            to="/compliance?customer_id=ALL"
            className="px-3 py-1.5 text-xs font-medium rounded-lg border border-slate-300 text-slate-600 hover:bg-slate-100 transition-colors"
          >
            Show all
          </Link>
        )}
      </div>

      <SarReviewPanel review={review} customerId={customerUrlId || undefined} />
    </PageShell>
  )
}
