import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import DataTable from "../components/DataTable";
import type { CustomerSummary, PaginatedResponse } from "../types";

export default function CustomersPage() {
  const navigate = useNavigate();
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [data, setData] = useState<PaginatedResponse<CustomerSummary> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);

  const fetchData = useCallback(async (p: number) => {
    setLoading(true);
    setError(null);
    try {
      const result = await api.get<PaginatedResponse<CustomerSummary>>("/api/customers", {
        first_name: firstName || undefined,
        last_name: lastName || undefined,
        page: p, per_page: 25,
      });
      setData(result);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, [firstName, lastName]);

  useEffect(() => { fetchData(page); }, [page, fetchData]);

  const handleSearch = () => { setPage(1); fetchData(1); };

  const columns = [
    { key: "customer_id", label: "Customer ID", render: (row: CustomerSummary) =>
        <button onClick={() => navigate(`/customers/${row.customer_id}`)} className="text-blue-600 hover:text-blue-800 hover:underline font-mono text-xs">
          {row.customer_id}
        </button>,
    },
    { key: "first_name", label: "First Name" },
    { key: "last_name", label: "Last Name" },
    { key: "city", label: "City", render: (row: CustomerSummary) => row.city || "-" },
    { key: "state", label: "State", render: (row: CustomerSummary) => row.state || "-" },
  ];

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-xl font-bold text-slate-800">Customers</h2>
        <p className="text-sm text-slate-500 mt-0.5">Search and view customer information</p>
      </div>

      <div className="bg-white border border-slate-200 rounded-lg p-4 space-y-3">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <input placeholder="First Name" value={firstName} onChange={e => setFirstName(e.target.value)}
            className="px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500" />
          <input placeholder="Last Name" value={lastName} onChange={e => setLastName(e.target.value)}
            className="px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500" />
        </div>
        <button onClick={handleSearch}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors">
          Search
        </button>
      </div>

      <DataTable
        columns={columns}
        data={data?.items || []}
        loading={loading}
        error={error}
        onRetry={() => fetchData(page)}
        emptyMessage="No customers found. Try a different name."
        page={data?.page}
        perPage={data?.per_page}
        total={data?.total}
        onPageChange={(p) => setPage(p)}
      />
    </div>
  );
}
