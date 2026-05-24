import { useState, useEffect, useCallback } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import DataTable from "../components/DataTable";
import type { TransactionRow, PaginatedResponse } from "../types";

export default function TransactionsPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const [sourceTxnId, setSourceTxnId] = useState(searchParams.get("source_txn_id") || "");
  const [accountId, setAccountId] = useState(searchParams.get("account_id") || "");
  const [customerId, setCustomerId] = useState(searchParams.get("customer_id") || "");
  const [amountMin, setAmountMin] = useState(searchParams.get("amount_min") || "");
  const [amountMax, setAmountMax] = useState(searchParams.get("amount_max") || "");
  const [counterparty, setCounterparty] = useState(searchParams.get("counterparty") || "");
  const [fromDate, setFromDate] = useState(searchParams.get("from_date") || "");
  const [toDate, setToDate] = useState(searchParams.get("to_date") || "");

  const [data, setData] = useState<PaginatedResponse<TransactionRow> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(Number(searchParams.get("page")) || 1);

  const fetchData = useCallback(async (p: number) => {
    setLoading(true);
    setError(null);
    try {
      const result = await api.get<PaginatedResponse<TransactionRow>>("/api/transactions", {
        source_txn_id: sourceTxnId || undefined,
        account_id: accountId || undefined,
        customer_id: customerId || undefined,
        amount_min: amountMin || undefined,
        amount_max: amountMax || undefined,
        counterparty: counterparty || undefined,
        from_date: fromDate || undefined,
        to_date: toDate || undefined,
        page: p,
        per_page: 25,
      });
      setData(result);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, [sourceTxnId, accountId, customerId, amountMin, amountMax, counterparty, fromDate, toDate]);

  useEffect(() => { fetchData(page); }, [page, fetchData]);

  const handleSearch = () => {
    setPage(1);
    const params: Record<string, string> = {};
    if (sourceTxnId) params.source_txn_id = sourceTxnId;
    if (accountId) params.account_id = accountId;
    if (customerId) params.customer_id = customerId;
    if (amountMin) params.amount_min = amountMin;
    if (amountMax) params.amount_max = amountMax;
    if (counterparty) params.counterparty = counterparty;
    if (fromDate) params.from_date = fromDate;
    if (toDate) params.to_date = toDate;
    setSearchParams(params);
    fetchData(1);
  };

  const filters: { label: string; onRemove: () => void }[] = [];
  if (sourceTxnId) filters.push({ label: `source_txn_id: ${sourceTxnId}`, onRemove: () => { setSourceTxnId(""); setPage(1); }});
  if (accountId) filters.push({ label: `account_id: ${accountId}`, onRemove: () => { setAccountId(""); setPage(1); }});
  if (customerId) filters.push({ label: `customer_id: ${customerId}`, onRemove: () => { setCustomerId(""); setPage(1); }});
  if (amountMin) filters.push({ label: `amount \u2265 $${amountMin}`, onRemove: () => { setAmountMin(""); setPage(1); }});
  if (amountMax) filters.push({ label: `amount \u2264 $${amountMax}`, onRemove: () => { setAmountMax(""); setPage(1); }});
  if (counterparty) filters.push({ label: `counterparty: ${counterparty}`, onRemove: () => { setCounterparty(""); setPage(1); }});
  if (fromDate) filters.push({ label: `from: ${fromDate}`, onRemove: () => { setFromDate(""); setPage(1); }});
  if (toDate) filters.push({ label: `to: ${toDate}`, onRemove: () => { setToDate(""); setPage(1); }});

  const columns = [
    { key: "source_txn_id", label: "Source ID", className: "font-mono text-xs" },
    { key: "account_name", label: "Account", render: (row: TransactionRow) =>
        row.account_name ? (
          <button onClick={() => navigate(`/customers/${row.customer_id}`)} className="text-blue-600 hover:text-blue-800 hover:underline">
            {row.account_name}
          </button>
        ) : row.account_id,
    },
    { key: "customer_id", label: "Customer", className: "font-mono text-xs" },
    { key: "amount", label: "Amount", render: (row: TransactionRow) =>
        row.amount != null ? <span className="font-medium tabular-nums">${row.amount.toLocaleString()}</span> : "-",
      className: "text-right tabular-nums",
    },
    { key: "counterparty", label: "Counterparty" },
    { key: "date", label: "Date", render: (row: TransactionRow) => row.date || "-", className: "text-slate-500" },
    { key: "location", label: "Location", sortable: false, render: (row: TransactionRow) =>
        [row.city, row.state, row.country].filter(Boolean).join(", ") || "-",
      className: "text-slate-500",
    },
  ];

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <h2 className="text-xl font-bold text-slate-800">Transactions</h2>
        <span className="inline-flex items-center px-2 py-0.5 text-xs font-bold bg-amber-100 text-amber-700 rounded-full border border-amber-300">
          DEV ONLY
        </span>
      </div>
      <p className="text-sm text-slate-500 mt-0.5">Search and review all transactions</p>

      {/* Search Form */}
      <div className="bg-white border border-slate-200 rounded-lg p-4 space-y-3">
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <input placeholder="Source TXN ID" value={sourceTxnId} onChange={e => setSourceTxnId(e.target.value)}
            className="px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500" />
          <input placeholder="Account ID" value={accountId} onChange={e => setAccountId(e.target.value)}
            className="px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500" />
          <input placeholder="Customer ID" value={customerId} onChange={e => setCustomerId(e.target.value)}
            className="px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500" />
          <input placeholder="Counterparty" value={counterparty} onChange={e => setCounterparty(e.target.value)}
            className="px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500" />
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <input type="number" placeholder="Min Amount" value={amountMin} onChange={e => setAmountMin(e.target.value)}
            className="px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500" />
          <input type="number" placeholder="Max Amount" value={amountMax} onChange={e => setAmountMax(e.target.value)}
            className="px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500" />
          <input type="date" placeholder="From" value={fromDate} onChange={e => setFromDate(e.target.value)}
            className="px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500" />
          <input type="date" placeholder="To" value={toDate} onChange={e => setToDate(e.target.value)}
            className="px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500" />
        </div>
        <button onClick={handleSearch}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors">
          Search
        </button>
      </div>

      {/* Active Filters */}
      {filters.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {filters.map((f, i) => (
            <span key={i} className="inline-flex items-center gap-1 px-2.5 py-1 bg-blue-50 text-blue-700 text-xs font-medium rounded-full">
              {f.label}
              <button onClick={f.onRemove} className="hover:text-blue-900 ml-0.5">&times;</button>
            </span>
          ))}
        </div>
      )}

      <DataTable
        columns={columns}
        data={data?.items || []}
        loading={loading}
        error={error}
        onRetry={() => fetchData(page)}
        emptyMessage="No transactions match your search. Try different filters."
        page={data?.page}
        perPage={data?.per_page}
        total={data?.total}
        onPageChange={(p) => { setPage(p); window.scrollTo(0, 0); }}
      />
    </div>
  );
}
