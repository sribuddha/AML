import { useState, useEffect, useCallback } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api, ApiError } from "../api/client";
import ReviewCard from "../components/ReviewCard";
import type { PendingSAR, PaginatedResponse } from "../types";

export default function CompliancePage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const uploadId = searchParams.get("upload_id");
  const customerUrlId = searchParams.get("customer_id") || "";
  const [customerInput, setCustomerInput] = useState(customerUrlId);

  const [sars, setSars] = useState<PendingSAR[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reviewing, setReviewing] = useState<string | null>(null);
  const [batchReviewing, setBatchReviewing] = useState(false);
  const [completed, setCompleted] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [riskFilter, setRiskFilter] = useState<string>("all");
  const [customerName, setCustomerName] = useState<string>("");

  const filteredSars = riskFilter === "all"
    ? sars
    : sars.filter(s => s.risk_level === riskFilter);

  const customerDisplayName = customerName || customerUrlId;

  const fetchSars = useCallback(async () => {
    setLoading(true);
    setError(null);
    if (!customerUrlId) {
      setCustomerName("");
    }
    try {
      const result = await api.get<PaginatedResponse<PendingSAR>>("/api/sar/pending", {
        upload_id: uploadId || undefined,
        customer_id: customerUrlId || undefined,
        per_page: 100,
      });
      setSars(result.items);
      setCompleted(result.items.length === 0);
      if (result.items.length > 0 && result.items[0].customer_first_name) {
        setCustomerName(`${result.items[0].customer_first_name} ${result.items[0].customer_last_name}`);
      }
    } catch (e: unknown) {
      if (e instanceof ApiError && e.status === 404) {
        setCompleted(true);
      } else {
        setError(e instanceof Error ? e.message : "Failed to load");
      }
    } finally {
      setLoading(false);
    }
  }, [uploadId, customerUrlId]);

  useEffect(() => { fetchSars(); }, [fetchSars]);

  const toggleSelect = (id: string) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (selectedIds.size === filteredSars.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(filteredSars.map(s => s.sar_id)));
    }
  };

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

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-slate-800">Compliance</h2>
          <p className="text-sm text-slate-500 mt-0.5">
            {uploadId ? `Upload: ${uploadId}` : "All pending reviews"}
            {customerUrlId && !uploadId && (
              <span className="inline-flex items-center gap-1 ml-2 px-2 py-0.5 bg-blue-50 text-blue-700 rounded-full text-xs font-medium">
                {customerDisplayName}
                <button onClick={() => { setCustomerInput(""); setSearchParams(prev => { prev.delete("customer_id"); return prev; }); }}
                  className="hover:text-blue-900 leading-none">&times;</button>
              </span>
            )}
          </p>
        </div>
        {!loading && sars.length > 0 && (
          <span className="text-sm text-slate-500">
            {sars.length} pending{riskFilter !== "all" ? ` (${filteredSars.length} ${riskFilter})` : ""}
          </span>
        )}
      </div>

      {loading && (
        <div className="space-y-4">
          {[1, 2, 3].map(i => (
            <div key={i} className="bg-white border border-slate-200 rounded-lg p-5 space-y-3">
              <div className="h-4 bg-slate-200 rounded w-48 animate-pulse" />
              <div className="h-4 bg-slate-200 rounded w-96 animate-pulse" />
              <div className="h-4 bg-slate-200 rounded w-64 animate-pulse" />
            </div>
          ))}
        </div>
      )}

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-center justify-between">
          <span className="text-sm text-red-700">{error}</span>
          <button onClick={fetchSars} className="text-sm font-medium text-red-700 hover:text-red-900">
            Retry
          </button>
        </div>
      )}

      {!loading && !error && completed && (
        <div className="bg-green-50 border border-green-200 rounded-lg p-8 text-center">
          <div className="text-3xl mb-2">&#9989;</div>
          <h3 className="text-lg font-semibold text-green-800 mb-1">You are all up to date.</h3>
          {customerUrlId && (
            <Link to="/compliance" className="mt-3 inline-block text-sm text-blue-600 hover:text-blue-800 underline">
              View all pending reviews
            </Link>
          )}
        </div>
      )}

      {!loading && !error && !completed && sars.length > 0 && (
        <div className="space-y-3">
          {/* Risk filter pills */}
          <div className="flex items-center gap-2">
            {["all", "high", "medium", "low"].map(level => (
              <button key={level} onClick={() => setRiskFilter(level)}
                className={`px-3 py-1 text-xs font-medium rounded-full transition-colors ${
                  riskFilter === level
                    ? level === "all" ? "bg-slate-800 text-white"
                      : level === "high" ? "bg-red-600 text-white"
                      : level === "medium" ? "bg-amber-500 text-white"
                      : "bg-green-600 text-white"
                    : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                }`}>
                {level === "all" ? "All" : level.charAt(0).toUpperCase() + level.slice(1)}
              </button>
            ))}
          </div>

          {/* Customer filter */}
          <div className="flex items-center gap-2">
            <input type="text" value={customerInput}
              onChange={e => setCustomerInput(e.target.value)}
              onKeyDown={e => { if (e.key === "Enter") setSearchParams(prev => { prev.set("customer_id", customerInput); return prev; }); }}
              placeholder="Filter by customer ID..."
              className="flex-1 max-w-xs px-3 py-1.5 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent" />
            <button onClick={() => { setSearchParams(prev => { prev.set("customer_id", customerInput); return prev; }); }}
              className="px-3 py-1.5 text-xs font-medium rounded-lg bg-blue-600 text-white hover:bg-blue-700 transition-colors">
              Filter
            </button>
            {customerUrlId && (
              <button onClick={() => { setCustomerInput(""); setSearchParams(prev => { prev.delete("customer_id"); return prev; }); }}
                className="px-3 py-1.5 text-xs font-medium rounded-lg border border-slate-300 text-slate-600 hover:bg-slate-100 transition-colors">
                Clear
              </button>
            )}
          </div>

          <div className="flex items-center justify-between">
            <label className="flex items-center gap-2 text-sm text-slate-600 cursor-pointer">
              <input type="checkbox" checked={selectedIds.size > 0 && selectedIds.size === filteredSars.length}
                onChange={toggleSelectAll}
                className="rounded border-slate-300 text-blue-600 focus:ring-blue-500" />
              {selectedIds.size > 0 ? `${selectedIds.size} selected` : "Select all"}
            </label>
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
          </div>

          <div className="space-y-3">
            {filteredSars.map(sar => (
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
        </div>
      )}
    </div>
  );
}
