import { useState, useEffect, useCallback } from "react";
import { useSearchParams } from "react-router-dom";
import { api, ApiError } from "../api/client";
import ReviewCard from "../components/ReviewCard";
import type { PendingSAR, PaginatedResponse } from "../types";

export default function CompliancePage() {
  const [searchParams] = useSearchParams();
  const uploadId = searchParams.get("upload_id");

  const [sars, setSars] = useState<PendingSAR[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reviewing, setReviewing] = useState<string | null>(null);
  const [completed, setCompleted] = useState(false);

  const fetchSars = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await api.get<PaginatedResponse<PendingSAR>>("/api/sar/pending", {
        upload_id: uploadId || undefined,
        per_page: 100,
      });
      setSars(result.items);
      setCompleted(result.items.length === 0);
    } catch (e: unknown) {
      if (e instanceof ApiError && e.status === 404) {
        setCompleted(true);
      } else {
        setError(e instanceof Error ? e.message : "Failed to load");
      }
    } finally {
      setLoading(false);
    }
  }, [uploadId]);

  useEffect(() => { fetchSars(); }, [fetchSars]);

  const handleReview = async (sarId: string, action: string) => {
    setReviewing(sarId);
    try {
      await api.patch(`/api/sar/${sarId}/review`, { action, notes: "" });
      await new Promise(r => setTimeout(r, 2000));
      setReviewing(null);
      await fetchSars();
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Review failed";
      alert(msg);
      setReviewing(null);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-slate-800">Compliance</h2>
          <p className="text-sm text-slate-500 mt-0.5">
            {uploadId ? `Upload: ${uploadId}` : "All pending reviews"}
          </p>
        </div>
        {!loading && sars.length > 0 && (
          <span className="text-sm text-slate-500">{sars.length} pending</span>
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
        </div>
      )}

      <div className="space-y-3">
        {sars.map(sar => (
          <ReviewCard
            key={sar.sar_id}
            sar={sar}
            onReview={(action) => handleReview(sar.sar_id, action)}
            reviewing={reviewing === sar.sar_id}
          />
        ))}
      </div>
    </div>
  );
}
