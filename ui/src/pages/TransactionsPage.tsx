import { useState, useCallback } from "react"
import { useSearchParams, useNavigate } from "react-router-dom"
import { api } from "../api/client"
import DataTable from "../components/DataTable"
import PageShell from "../components/PageShell"
import SearchForm from "../components/SearchForm"
import type { TransactionRow, PaginatedResponse } from "../types"

export default function TransactionsPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()

  const [filters, setFilters] = useState<Record<string, string>>({
    source_txn_id: searchParams.get("source_txn_id") || "",
    account_id: searchParams.get("account_id") || "",
    customer_id: searchParams.get("customer_id") || "",
    amount_min: searchParams.get("amount_min") || "",
    amount_max: searchParams.get("amount_max") || "",
    counterparty: searchParams.get("counterparty") || "",
    from_date: searchParams.get("from_date") || "",
    to_date: searchParams.get("to_date") || "",
  })

  const [data, setData] = useState<PaginatedResponse<TransactionRow> | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [page, setPage] = useState(1)

  const fetchTxns = useCallback(async (p: number) => {
    setLoading(true)
    setError(null)
    try {
      const params: Record<string, string | number | undefined> = { page: p, per_page: 50 }
      for (const [k, v] of Object.entries(filters)) {
        if (v) params[k] = v
      }
      const result = await api.get<PaginatedResponse<TransactionRow>>("/api/transactions", params)
      setData(result)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load")
    } finally {
      setLoading(false)
    }
  }, [filters])

  const handleSearch = () => { setPage(1); fetchTxns(1); window.scrollTo(0, 0) }

  const handleFilterChange = (key: string, value: string) => {
    setFilters((prev) => ({ ...prev, [key]: value }))
  }

  const transactionColumns = [
    { key: "source_txn_id", label: "Source ID" },
    {
      key: "account_name", label: "Account",
      render: (row: TransactionRow) => (
        <button onClick={() => navigate(`/transactions?account_id=${row.account_id}`)}
          className="text-blue-600 hover:text-blue-800 hover:underline font-mono text-xs">
          {row.account_name || row.account_id}
        </button>
      ),
    },
    {
      key: "customer_id", label: "Customer",
      render: (row: TransactionRow) => (
        <button onClick={() => navigate(`/customers/${row.customer_id}`)}
          className="text-blue-600 hover:text-blue-800 hover:underline font-mono text-xs">
          {row.customer_id}
        </button>
      ),
    },
    {
      key: "amount", label: "Amount",
      render: (row: TransactionRow) =>
        row.amount != null ? `$${row.amount.toLocaleString(undefined, { minimumFractionDigits: 2 })}` : "-",
      className: "text-right font-mono tabular-nums",
    },
    { key: "counterparty", label: "Counterparty" },
    { key: "date", label: "Date" },
    {
      key: "location", label: "Location",
      render: (row: TransactionRow) => [row.city, row.state, row.country].filter(Boolean).join(", ") || "-",
    },
  ]

  const searchFields = [
    { key: "source_txn_id", label: "Source ID", placeholder: "TXN-..." },
    { key: "account_id", label: "Account ID" },
    { key: "customer_id", label: "Customer ID" },
    { key: "counterparty", label: "Counterparty" },
    { key: "amount_min", label: "Min Amount" },
    { key: "amount_max", label: "Max Amount" },
    { key: "from_date", label: "From", type: "date" as const },
    { key: "to_date", label: "To", type: "date" as const },
  ]

  return (
    <PageShell
      title="Transactions"
      description="DEV ONLY"
    >
      <SearchForm
        fields={searchFields}
        values={filters}
        onChange={handleFilterChange}
        onSearch={handleSearch}
        columns={4}
      />

      <DataTable
        columns={transactionColumns}
        data={data?.items || []}
        loading={loading}
        error={error}
        onRetry={() => fetchTxns(page)}
        emptyMessage="No transactions found."
        page={data?.page}
        perPage={data?.per_page}
        total={data?.total}
        onPageChange={(p) => setPage(p)}
      />
    </PageShell>
  )
}
