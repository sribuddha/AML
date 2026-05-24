import { useState, useCallback, useEffect, useRef } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import DataTable from "../components/DataTable";
import StatusBadge from "../components/StatusBadge";
import FileUploader from "../components/FileUploader";
import type { UploadSummary, PaginatedResponse, EvalReport } from "../types";

const STATUS_TABS = ["All", "Uploaded", "Processing", "Pending Review", "Complete", "Failed"];

export default function OperationsPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const initialTabIsSearch = useRef(searchParams.get("tab") === "search");
  const [activeTab, setActiveTab] = useState<"upload" | "search">(
    initialTabIsSearch.current ? "search" : "upload"
  );

  const [uploadId, setUploadId] = useState("");
  const [statusTab, setStatusTab] = useState("All");
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const [data, setData] = useState<PaginatedResponse<UploadSummary> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [uploadResult, setUploadResult] = useState<{ total_rows: number; accepted_count: number; failed_count: number } | null>(null);
  const [searched, setSearched] = useState(false);

  const [evalModal, setEvalModal] = useState<{ uploadId: string; report: EvalReport | null; loading: boolean; error: string | null } | null>(null);

  const fetchUploads = useCallback(async (p: number) => {
    setLoading(true);
    setError(null);
    setSearched(true);
    try {
      const result = await api.get<PaginatedResponse<UploadSummary>>("/api/uploads/search", {
        upload_id: uploadId || undefined,
        status: statusTab === "All" ? undefined : statusTab.toLowerCase().replace(" ", "_"),
        from_date: fromDate || undefined,
        to_date: toDate || undefined,
        page: p, per_page: 25,
      });
      setData(result);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, [uploadId, statusTab, fromDate, toDate]);

  const handleSearch = () => { setPage(1); fetchUploads(1); };

  useEffect(() => {
    if (initialTabIsSearch.current) {
      fetchUploads(1);
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const handleUploadWithResult = async (file: File) => {
    try {
      const result = await api.upload<{ total_rows: number; accepted_count: number; failed_count: number }>("/api/uploads", file);
      setUploadResult(result);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Upload failed";
      alert(msg);
    }
  };

  const handleEval = async (uploadId: string) => {
    setEvalModal({ uploadId, report: null, loading: true, error: null });
    try {
      const report = await api.post<EvalReport>(`/api/uploads/${uploadId}/eval`);
      setEvalModal({ uploadId, report, loading: false, error: null });
    } catch (e: unknown) {
      setEvalModal({ uploadId, report: null, loading: false, error: e instanceof Error ? e.message : "Eval failed" });
    }
  };

  const uploadColumns = [
    { key: "id", label: "Upload ID", sortable: false, render: (row: UploadSummary) =>
        row.status === "pending_human" ? (
          <button onClick={() => navigate(`/compliance?upload_id=${row.id}`)} className="text-blue-600 hover:text-blue-800 hover:underline font-mono text-[10px]">
            {row.id}
          </button>
        ) : (
          <span className="font-mono text-[10px] text-slate-500">{row.id}</span>
        ),
    },
    { key: "filename", label: "Filename" },
    { key: "status", label: "Status", render: (row: UploadSummary) => <StatusBadge status={row.status} /> },
    { key: "total_rows", label: "Total", className: "text-right" },
    { key: "accepted_count", label: "Accepted", className: "text-right" },
    { key: "failed_count", label: "Failed", className: "text-right" },
    { key: "uploaded_at", label: "Uploaded", render: (row: UploadSummary) =>
        row.uploaded_at ? row.uploaded_at.replace(/\.\d+/, "").replace(/Z$/, "") : "-",
      className: "text-slate-500" },
    { key: "pending_sar_count", label: "Pending", sortable: false, render: (row: UploadSummary) =>
        row.status === "pending_human" ? (
          <span className="inline-flex items-center justify-center min-w-[22px] h-5 px-1.5 bg-amber-100 text-amber-700 text-xs font-bold rounded-full">
            {row.pending_sar_count}
          </span>
        ) : (
          <span className="text-slate-300">-</span>
        ),
    },
    { key: "eval", label: "Eval", sortable: false, render: (row: UploadSummary) =>
        row.eval_file && row.status === "complete" ? (
          <button onClick={() => handleEval(row.id)}
            className="px-2 py-1 text-xs font-medium bg-indigo-50 text-indigo-600 border border-indigo-200 rounded hover:bg-indigo-100 transition-colors">
            Eval
          </button>
        ) : null,
    },
  ];

  const renderContent = () => {
    if (activeTab === "upload") {
      return (
        <div className="space-y-4">
          <FileUploader onUpload={handleUploadWithResult} />
          {uploadResult && (
            <div className="bg-white border border-slate-200 rounded-lg p-5">
              <h3 className="text-sm font-semibold text-slate-500 uppercase tracking-wider mb-3">Upload Result</h3>
              <div className="flex gap-6">
                <div className="text-center">
                  <div className="text-2xl font-bold text-slate-800">{uploadResult.total_rows}</div>
                  <div className="text-xs text-slate-500">Total Rows</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold text-green-600">{uploadResult.accepted_count}</div>
                  <div className="text-xs text-slate-500">Accepted</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold text-red-600">{uploadResult.failed_count}</div>
                  <div className="text-xs text-slate-500">Failed</div>
                </div>
              </div>
              <button onClick={() => setActiveTab("search")} className="mt-4 text-sm text-blue-600 hover:text-blue-800 hover:underline">
                View Uploads &rarr;
              </button>
            </div>
          )}
        </div>
      );
    }
    return (
      <div className="space-y-4">
        <div className="flex flex-wrap gap-1">
          {STATUS_TABS.map(s => (
            <button key={s} onClick={() => { setStatusTab(s); setPage(1); }}
              className={`px-3 py-1.5 text-xs font-medium rounded-full transition-colors ${
                statusTab === s
                  ? "bg-blue-600 text-white"
                  : "bg-slate-100 text-slate-600 hover:bg-slate-200"
              }`}>
              {s}
            </button>
          ))}
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <input placeholder="Upload ID" value={uploadId} onChange={e => setUploadId(e.target.value)}
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

        {!searched ? (
          <div className="bg-slate-50 border border-slate-200 rounded-lg p-8 text-center">
            <span className="text-2xl">&#128269;</span>
            <p className="text-sm text-slate-500 mt-2">Enter an Upload ID, select a date range, and click Search to find uploads.</p>
          </div>
        ) : (
          <DataTable
            columns={uploadColumns}
            data={data?.items || []}
            loading={loading}
            error={error}
            onRetry={() => fetchUploads(page)}
            emptyMessage="No uploads found."
            page={data?.page}
            perPage={data?.per_page}
            total={data?.total}
            onPageChange={(p) => setPage(p)}
          />
        )}
      </div>
    );
  };

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-xl font-bold text-slate-800">Operations</h2>
        <p className="text-sm text-slate-500 mt-0.5">Upload files and manage uploads</p>
      </div>

      <div className="flex gap-1 bg-slate-100 rounded-lg p-1 w-fit">
        <button onClick={() => setActiveTab("upload")}
          className={`px-4 py-2 text-sm font-medium rounded-md transition-colors ${
            activeTab === "upload" ? "bg-white text-slate-800 shadow-sm" : "text-slate-500 hover:text-slate-700"
          }`}>
          Upload
        </button>
        <button onClick={() => setActiveTab("search")}
          className={`px-4 py-2 text-sm font-medium rounded-md transition-colors ${
            activeTab === "search" ? "bg-white text-slate-800 shadow-sm" : "text-slate-500 hover:text-slate-700"
          }`}>
          Search Uploads
        </button>
      </div>

      {renderContent()}

      {/* Eval modal */}
      {evalModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={() => setEvalModal(null)}>
          <div className="bg-white rounded-lg shadow-xl max-w-3xl w-full max-h-[85vh] overflow-auto mx-4" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200">
              <h3 className="text-lg font-semibold text-slate-800">Eval Report</h3>
              <button onClick={() => setEvalModal(null)} className="text-slate-400 hover:text-slate-600 text-xl leading-none">&times;</button>
            </div>
            <div className="p-6 space-y-6">
              {evalModal.loading && (
                <div className="flex items-center gap-3 text-sm text-slate-500">
                  <div className="w-4 h-4 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
                  Running evaluation...
                </div>
              )}
              {evalModal.error && (
                <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-sm text-red-700">{evalModal.error}</div>
              )}
              {evalModal.report && (
                <>
                  {/* Summary cards */}
                  <div className="grid grid-cols-3 gap-4">
                    <div className="bg-slate-50 rounded-lg p-3 text-center">
                      <div className="text-2xl font-bold text-slate-800">{evalModal.report.total_transactions}</div>
                      <div className="text-xs text-slate-500">Transactions</div>
                    </div>
                    <div className="bg-slate-50 rounded-lg p-3 text-center">
                      <div className="text-2xl font-bold text-red-600">{evalModal.report.total_anomalous}</div>
                      <div className="text-xs text-slate-500">Anomalous (expected)</div>
                    </div>
                    <div className="bg-slate-50 rounded-lg p-3 text-center">
                      <div className="text-2xl font-bold text-amber-600">{evalModal.report.total_flagged}</div>
                      <div className="text-xs text-slate-500">Flagged (actual)</div>
                    </div>
                  </div>

                  {/* Overall metrics */}
                  <div className="grid grid-cols-3 gap-4">
                    <div className="bg-indigo-50 rounded-lg p-3 text-center">
                      <div className="text-2xl font-bold text-indigo-700">{(evalModal.report.overall_precision * 100).toFixed(1)}%</div>
                      <div className="text-xs text-indigo-500">Precision</div>
                    </div>
                    <div className="bg-indigo-50 rounded-lg p-3 text-center">
                      <div className="text-2xl font-bold text-indigo-700">{(evalModal.report.overall_recall * 100).toFixed(1)}%</div>
                      <div className="text-xs text-indigo-500">Recall</div>
                    </div>
                    <div className="bg-indigo-50 rounded-lg p-3 text-center">
                      <div className="text-2xl font-bold text-indigo-700">{(evalModal.report.overall_f1 * 100).toFixed(1)}%</div>
                      <div className="text-xs text-indigo-500">F1 Score</div>
                    </div>
                  </div>

                  {/* Hallucination + Completeness */}
                  <div className="grid grid-cols-2 gap-4">
                    <div className="bg-teal-50 rounded-lg p-3 text-center">
                      <div className="text-2xl font-bold text-teal-700">{(evalModal.report.hallucination_free_rate * 100).toFixed(1)}%</div>
                      <div className="text-xs text-teal-500">Hallucination-Free</div>
                    </div>
                    <div className="bg-teal-50 rounded-lg p-3 text-center">
                      <div className="text-2xl font-bold text-teal-700">{(evalModal.report.avg_completeness * 100).toFixed(1)}%</div>
                      <div className="text-xs text-teal-500">Avg Completeness</div>
                    </div>
                  </div>

                  {/* Pattern metrics table */}
                  {evalModal.report.pattern_metrics.length > 0 && (
                    <div>
                      <h4 className="text-sm font-semibold text-slate-500 uppercase tracking-wider mb-2">Pattern Metrics</h4>
                      <div className="overflow-auto border border-slate-200 rounded-lg">
                        <table className="w-full text-xs">
                          <thead className="bg-slate-50">
                            <tr>
                              <th className="px-3 py-2 text-left font-medium text-slate-600">Pattern</th>
                              <th className="px-3 py-2 text-right font-medium text-slate-600">Total</th>
                              <th className="px-3 py-2 text-right font-medium text-slate-600">Flagged</th>
                              <th className="px-3 py-2 text-right font-medium text-slate-600">Precision</th>
                              <th className="px-3 py-2 text-right font-medium text-slate-600">Recall</th>
                              <th className="px-3 py-2 text-right font-medium text-slate-600">F1</th>
                            </tr>
                          </thead>
                          <tbody>
                            {evalModal.report.pattern_metrics.map((pm, i) => (
                              <tr key={i} className={i % 2 === 0 ? "bg-white" : "bg-slate-50/50"}>
                                <td className="px-3 py-1.5 text-slate-700 border-b border-slate-100">{pm.pattern}</td>
                                <td className="px-3 py-1.5 text-right text-slate-700 border-b border-slate-100">{pm.total}</td>
                                <td className="px-3 py-1.5 text-right text-slate-700 border-b border-slate-100">{pm.flagged}</td>
                                <td className="px-3 py-1.5 text-right border-b border-slate-100">
                                  <span className={`${pm.precision >= 0.8 ? "text-green-600" : pm.precision >= 0.5 ? "text-amber-600" : "text-red-600"}`}>
                                    {(pm.precision * 100).toFixed(1)}%</span>
                                </td>
                                <td className="px-3 py-1.5 text-right border-b border-slate-100">
                                  <span className={`${pm.recall >= 0.8 ? "text-green-600" : pm.recall >= 0.5 ? "text-amber-600" : "text-red-600"}`}>
                                    {(pm.recall * 100).toFixed(1)}%</span>
                                </td>
                                <td className="px-3 py-1.5 text-right border-b border-slate-100">
                                  <span className={`${pm.f1 >= 0.8 ? "text-green-600" : pm.f1 >= 0.5 ? "text-amber-600" : "text-red-600"}`}>
                                    {(pm.f1 * 100).toFixed(1)}%</span>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}

                  {/* Hallucination results */}
                  {evalModal.report.hallucination_results.filter(h => !h.passed).length > 0 && (
                    <div>
                      <h4 className="text-sm font-semibold text-slate-500 uppercase tracking-wider mb-2">Hallucination Issues</h4>
                      <div className="space-y-2">
                        {evalModal.report.hallucination_results.filter(h => !h.passed).map(h => (
                          <div key={h.sar_id} className="bg-red-50 border border-red-200 rounded-lg px-3 py-2">
                            <div className="text-xs font-mono text-red-700">SAR {h.sar_id.substring(0, 8)}...</div>
                            <div className="text-xs text-red-600 mt-1">Hallucinated facts: {h.hallucinated_facts.join(", ")}</div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Completeness issues */}
                  {evalModal.report.completeness_results.filter(c => c.score < 1).length > 0 && (
                    <div>
                      <h4 className="text-sm font-semibold text-slate-500 uppercase tracking-wider mb-2">Completeness Issues</h4>
                      <div className="space-y-2">
                        {evalModal.report.completeness_results.filter(c => c.score < 1).map(c => (
                          <div key={c.sar_id} className="bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
                            <div className="text-xs font-mono text-amber-700">SAR {c.sar_id.substring(0, 8)}... (score: {(c.score * 100).toFixed(0)}%)</div>
                            <div className="text-xs text-amber-600 mt-1">Missed rules: {c.missed_rules.join(", ") || "none"}</div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
