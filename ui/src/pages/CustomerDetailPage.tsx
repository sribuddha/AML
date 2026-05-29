import { useState, useEffect, useCallback } from "react"
import { useParams, useNavigate, Link } from "react-router-dom"
import { api, ApiError } from "../api/client"
import { useSarReview } from "../hooks/useSarReview"
import SarReviewPanel from "../components/SarReviewPanel"
import type { CustomerDetail, PaginatedResponse, PendingSAR } from "../types"

export default function CustomerDetailPage() {
  const { customerId } = useParams<{ customerId: string }>()
  const navigate = useNavigate()
  const [data, setData] = useState<CustomerDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!customerId) return
    setLoading(true)
    setError(null)
    api.get<CustomerDetail>(`/api/customers/${customerId}`)
      .then(setData)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoading(false))
  }, [customerId])

  const review = useSarReview({ customerId })

  if (loading) return (
    <div className="space-y-4">
      <div className="h-8 bg-slate-200 rounded w-48 animate-pulse" />
      <div className="bg-white rounded-lg border border-slate-200 p-6 space-y-4">
        <div className="h-4 bg-slate-200 rounded w-3/4 animate-pulse" />
        <div className="h-4 bg-slate-200 rounded w-1/2 animate-pulse" />
      </div>
    </div>
  )

  if (error) return (
    <div className="text-center py-12">
      <div className="text-red-500 text-lg mb-2">Failed to load customer</div>
      <p className="text-slate-500 text-sm mb-4">{error}</p>
      <button onClick={() => navigate("/customers")} className="text-blue-600 hover:text-blue-800 text-sm font-medium">
        &larr; Back to customers
      </button>
    </div>
  )

  if (!data) return (
    <div className="text-center py-12">
      <div className="text-slate-400 text-lg mb-2">Customer not found</div>
      <button onClick={() => navigate("/customers")} className="text-blue-600 hover:text-blue-800 text-sm font-medium">
        &larr; Back to customers
      </button>
    </div>
  )

  return (
    <div className="space-y-6">
      <Link to="/customers" className="text-sm text-blue-600 hover:text-blue-800 hover:underline">&larr; Back to customers</Link>

      <div>
        <h2 className="text-xl font-bold text-slate-800">{data.first_name} {data.last_name}</h2>
        <p className="text-sm text-slate-500">{data.customer_id}</p>
      </div>

      {/* Customer Info Card */}
      <div className="bg-white border border-slate-200 rounded-lg p-6">
        <h3 className="text-sm font-semibold text-slate-500 uppercase tracking-wider mb-3">Customer Information</h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <span className="text-xs text-slate-400 block">Address</span>
            <span className="text-sm text-slate-700">{data.address_line || "\u2014"}</span>
          </div>
          <div>
            <span className="text-xs text-slate-400 block">City</span>
            <span className="text-sm text-slate-700">{data.city || "\u2014"}</span>
          </div>
          <div>
            <span className="text-xs text-slate-400 block">State</span>
            <span className="text-sm text-slate-700">{data.state || "\u2014"}</span>
          </div>
          <div>
            <span className="text-xs text-slate-400 block">ZIP</span>
            <span className="text-sm text-slate-700">{data.zip || "\u2014"}</span>
          </div>
        </div>
      </div>

      {/* Accounts Table */}
      <div className="bg-white border border-slate-200 rounded-lg overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-100">
          <h3 className="text-sm font-semibold text-slate-500 uppercase tracking-wider">Accounts ({data.accounts.length})</h3>
        </div>
        {data.accounts.length === 0 ? (
          <div className="p-5 text-sm text-slate-400">No accounts found for this customer.</div>
        ) : (
          <table className="w-full">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-200">
                <th className="px-5 py-3 text-left text-xs font-semibold text-slate-500 uppercase">Account</th>
                <th className="px-5 py-3 text-left text-xs font-semibold text-slate-500 uppercase">Name</th>
                <th className="px-5 py-3 text-left text-xs font-semibold text-slate-500 uppercase">Bank</th>
                <th className="px-5 py-3 text-left text-xs font-semibold text-slate-500 uppercase">Type</th>
                <th className="px-5 py-3 text-left text-xs font-semibold text-slate-500 uppercase">Opened</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {data.accounts.map((acc) => (
                <tr key={acc.account_id} className="hover:bg-slate-50">
                  <td className="px-5 py-3">
                    <button
                      onClick={() => navigate(`/transactions?account_id=${acc.account_id}`)}
                      className="text-blue-600 hover:text-blue-800 hover:underline font-mono text-xs"
                    >
                      {acc.account_id}
                    </button>
                  </td>
                  <td className="px-5 py-3 text-sm text-slate-700">{acc.name || "\u2014"}</td>
                  <td className="px-5 py-3 text-sm text-slate-700">{acc.bank || "\u2014"}</td>
                  <td className="px-5 py-3 text-sm text-slate-700">{acc.type || "\u2014"}</td>
                  <td className="px-5 py-3 text-sm text-slate-700">{acc.date_opened || "\u2014"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Pending SARs */}
      <div className="bg-white border border-slate-200 rounded-lg p-5">
        <h3 className="text-sm font-semibold text-slate-500 uppercase tracking-wider mb-4">
          Pending SARs ({review.sars.length})
        </h3>
        {review.sars.length === 0 && !review.loading && !review.error ? (
          <p className="text-sm text-slate-400">No pending SARs for this customer.</p>
        ) : (
          <SarReviewPanel review={review} customerId={customerId} />
        )}
      </div>
    </div>
  )
}
