import { useState, useEffect, useCallback } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { api, ApiError } from "../api/client";
import ReviewCard from "../components/ReviewCard";
import type { CustomerDetail, PendingSAR, PaginatedResponse } from "../types";

export default function CustomerDetailPage() {
  const { customerId } = useParams<{ customerId: string }>();
  const navigate = useNavigate();
  const [data, setData] = useState<CustomerDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sars, setSars] = useState<PendingSAR[]>([]);
  const [sarsLoading, setSarsLoading] = useState(true);
  const [sarsError, setSarsError] = useState<string | null>(null);
  const [reviewing, setReviewing] = useState<string | null>(null);
  const [batchReviewing, setBatchReviewing] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  useEffect(() => {
    if (!customerId) return;
    setLoading(true);
    setError(null);
    api.get<CustomerDetail>(`/api/customers/${customerId}`)
      .then(setData)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoading(false));
  }, [customerId]);

  const fetchSars = useCallback(async () => {
    if (!customerId) return;
    setSarsLoading(true);
    setSarsError(null);
    try {
      const result = await api.get<PaginatedResponse<PendingSAR>>("/api/sar/pending", {
        customer_id: customerId,
        per_page: 100,
      });
      setSars(result.items);
    } catch (e: unknown) {
      if (e instanceof ApiError && e.status === 404) {
        setSars([]);
      } else {
        setSarsError(e instanceof Error ? e.message : "Failed to load");
      }
    } finally {
      setSarsLoading(false);
    }
  }, [customerId]);

  useEffect(() => { fetchSars(); }, [fetchSars]);

  const handleReview = async (sarId: string, action: string) => {
    setReviewing(sarId);
    try {
      await api.patch(`/api/sar/${sarId}/review`, { action, notes: "" });
      await new Promise(r => setTimeout(r, 1000));
      setReviewing(null);
      await fetchSars();
      setSelectedIds(new Set());
      window.dispatchEvent(new CustomEvent("sar-reviewed"));
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Review failed";
      alert(msg);
      setReviewing(null);
    }
  };

  const handleBatchReview = async (action: string) => {
    if (selectedIds.size === 0) return;
    setBatchReviewing(true);
    try {
      await api.post("/api/sar/batch-review", { sar_ids: Array.from(selectedIds), action });
      await new Promise(r => setTimeout(r, 1000));
      await fetchSars();
      setSelectedIds(new Set());
      window.dispatchEvent(new CustomEvent("sar-reviewed"));
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Batch review failed";
      alert(msg);
    } finally {
      setBatchReviewing(false);
    }
  };

  const toggleSelect = (id: string) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (selectedIds.size === sars.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(sars.map(s => s.sar_id)));
    }
  };

  if (loading) return (
    <div className="space-y-4">
      <div className="h-8 bg-slate-200 rounded w-48 animate-pulse" />
      <div className="bg-white rounded-lg border border-slate-200 p-6 space-y-4">
        <div className="h-4 bg-slate-200 rounded w-3/4 animate-pulse" />
        <div className="h-4 bg-slate-200 rounded w-1/2 animate-pulse" />
      </div>
    </div>
  );

  if (error) return (
    <div className="text-center py-12">
      <div className="text-red-500 text-lg mb-2">Failed to load customer</div>
      <p className="text-slate-500 text-sm mb-4">{error}</p>
      <button onClick={() => navigate("/customers")} className="text-blue-600 hover:text-blue-800 text-sm font-medium">
        &larr; Back to customers
      </button>
    </div>
  );

  if (!data) return (
    <div className="text-center py-12">
      <div className="text-slate-400 text-lg mb-2">Customer not found</div>
      <button onClick={() => navigate("/customers")} className="text-blue-600 hover:text-blue-800 text-sm font-medium">
        &larr; Back to customers
      </button>
    </div>
  );

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
      <div className="bg-white border border-slate-200 rounded-lg overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-slate-500 uppercase tracking-wider">Pending SARs ({sars.length})</h3>
          {sars.length > 0 && (
            <div className="flex gap-2">
              <button onClick={() => handleBatchReview("confirmed")}
                disabled={batchReviewing || selectedIds.size === 0}
                className="px-3 py-1.5 text-xs font-medium rounded-lg bg-green-600 text-white hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors">
                {batchReviewing ? "..." : "Accept All"}
              </button>
              <button onClick={() => handleBatchReview("dismissed")}
                disabled={batchReviewing || selectedIds.size === 0}
                className="px-3 py-1.5 text-xs font-medium rounded-lg border border-slate-300 text-slate-700 hover:bg-slate-100 disabled:opacity-50 disabled:cursor-not-allowed transition-colors">
                {batchReviewing ? "..." : "Dismiss All"}
              </button>
            </div>
          )}
        </div>

        {sarsLoading && (
          <div className="p-5 space-y-3">
            {[1, 2].map(i => (
              <div key={i} className="h-20 bg-slate-100 rounded animate-pulse" />
            ))}
          </div>
        )}

        {sarsError && (
          <div className="p-5 flex items-center justify-between">
            <span className="text-sm text-red-700">{sarsError}</span>
            <button onClick={fetchSars} className="text-sm font-medium text-red-700 hover:text-red-900">Retry</button>
          </div>
        )}

        {!sarsLoading && !sarsError && sars.length === 0 && (
          <div className="p-5 text-sm text-slate-400">No pending SARs for this customer.</div>
        )}

        {!sarsLoading && !sarsError && sars.length > 0 && (
          <div className="p-5 space-y-3">
            <label className="flex items-center gap-2 text-sm text-slate-600 cursor-pointer mb-3">
              <input type="checkbox" checked={selectedIds.size > 0 && selectedIds.size === sars.length}
                onChange={toggleSelectAll}
                className="rounded border-slate-300 text-blue-600 focus:ring-blue-500" />
              {selectedIds.size > 0 ? `${selectedIds.size} selected` : "Select all"}
            </label>
            {sars.map(sar => (
              <div key={sar.sar_id} className="flex items-start gap-3">
                <input type="checkbox" checked={selectedIds.has(sar.sar_id)}
                  onChange={() => toggleSelect(sar.sar_id)}
                  className="mt-5 ml-1 rounded border-slate-300 text-blue-600 focus:ring-blue-500 shrink-0" />
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
        )}
      </div>
    </div>
  );
}
