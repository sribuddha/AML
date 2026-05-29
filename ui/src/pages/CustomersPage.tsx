import { useState, useCallback } from "react"
import { useNavigate } from "react-router-dom"
import { api } from "../api/client"
import DataTable from "../components/DataTable"
import PageShell from "../components/PageShell"
import type { CustomerSummary, PaginatedResponse } from "../types"

export default function CustomersPage() {
  const navigate = useNavigate()
  const [firstName, setFirstName] = useState("")
  const [lastName, setLastName] = useState("")
  const [data, setData] = useState<PaginatedResponse<CustomerSummary> | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [page, setPage] = useState(1)
  const [searched, setSearched] = useState(false)

  const fetchCustomers = useCallback(async (p: number) => {
    setLoading(true)
    setError(null)
    setSearched(true)
    try {
      const result = await api.get<PaginatedResponse<CustomerSummary>>("/api/customers", {
        first_name: firstName || undefined,
        last_name: lastName || undefined,
        page: p, per_page: 25,
      })
      setData(result)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load")
    } finally {
      setLoading(false)
    }
  }, [firstName, lastName])

  return (
    <PageShell title="Customers" description="Search and browse customer records">
      <div className="flex gap-2">
        <input placeholder="First name" value={firstName}
          onChange={(e) => setFirstName(e.target.value)}
          className="px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500" />
        <input placeholder="Last name" value={lastName}
          onChange={(e) => setLastName(e.target.value)}
          className="px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500" />
        <button onClick={() => { setPage(1); fetchCustomers(1) }}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors">
          Search
        </button>
      </div>

      <DataTable
        columns={[
          {
            key: "customer_id", label: "Customer ID",
            render: (row: CustomerSummary) => (
              <button onClick={() => navigate(`/customers/${row.customer_id}`)}
                className="text-blue-600 hover:text-blue-800 hover:underline font-mono text-xs">
                {row.customer_id}
              </button>
            ),
          },
          {
            key: "name", label: "Name",
            render: (row: CustomerSummary) => `${row.first_name} ${row.last_name}`,
          },
          { key: "city", label: "City" },
          { key: "state", label: "State" },
        ]}
        data={data?.items || []}
        loading={loading}
        error={!searched ? null : error}
        onRetry={() => fetchCustomers(page)}
        emptyMessage={searched ? "No customers found." : ""}
        page={data?.page}
        perPage={data?.per_page}
        total={data?.total}
        onPageChange={(p) => setPage(p)}
      />
    </PageShell>
  )
}
