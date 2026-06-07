import { useState } from "react"
import { Link, useSearchParams } from "react-router-dom"
import { useSarReview } from "../hooks/useSarReview"
import SarReviewPanel from "../components/SarReviewPanel"
import AutoReviewedPanel from "../components/AutoReviewedPanel"
import TabSet, { type Tab } from "../components/TabSet"
import PageShell from "../components/PageShell"

const TABS: Tab[] = [
  { id: "pending", label: "Pending Review" },
  { id: "auto_reviewed", label: "Auto-Reviewed" },
]

export default function CompliancePage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const uploadId = searchParams.get("upload_id")
  const customerUrlId = searchParams.get("customer_id") || ""
  const customerInputParam = searchParams.get("customer_input") || customerUrlId
  const [customerInput, setCustomerInput] = useState(customerInputParam)
  const [tab, setTab] = useState("pending")

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
          {uploadId ? `Upload: ${uploadId}` : "Compliance Review"}
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
        tab === "pending" && !review.loading && review.sars.length > 0 ? (
          <span className="text-sm text-slate-500">
            {review.sars.length} pending
            {review.riskLevel !== "all" ? ` (${review.filteredSars.length} ${review.riskLevel})` : ""}
          </span>
        ) : undefined
      }
    >
      <div className="space-y-4">
        <TabSet tabs={TABS} active={tab} onChange={setTab} />

        {tab === "pending" && (
          <>
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
          </>
        )}

        {tab === "auto_reviewed" && (
          <AutoReviewedPanel
            uploadId={uploadId}
            onSelectUpload={(id) => setSearchParams((prev) => {
              if (id) { prev.set("upload_id", id) } else { prev.delete("upload_id") }
              return prev
            })}
          />
        )}
      </div>
    </PageShell>
  )
}
