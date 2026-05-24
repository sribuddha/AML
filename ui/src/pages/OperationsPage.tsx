import { useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import DataTable from "../components/DataTable";
import StatusBadge from "../components/StatusBadge";
import FileUploader from "../components/FileUploader";
import type { UploadSummary, PaginatedResponse } from "../types";

const STATUS_TABS = ["All", "Uploaded", "Processing", "Pending Review", "Complete", "Failed"];

export default function OperationsPage() {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<"upload" | "search">("upload");

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

  const handleUploadWithResult = async (file: File) => {
    try {
      const result = await api.upload<{ total_rows: number; accepted_count: number; failed_count: number }>("/api/uploads", file);
      setUploadResult(result);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Upload failed";
      alert(msg);
    }
  };

  const uploadColumns = [
    { key: "id", label: "Upload ID", render: (row: UploadSummary) =>
        row.status === "pending_human" ? (
          <button onClick={() => navigate(`/compliance?upload_id=${row.id}`)} className="text-blue-600 hover:text-blue-800 hover:underline font-mono text-xs">
            {row.id.substring(0, 8)}&hellip;
          </button>
        ) : (
          <span className="font-mono text-xs text-slate-500">{row.id.substring(0, 8)}&hellip;</span>
        ),
    },
    { key: "filename", label: "Filename" },
    { key: "status", label: "Status", render: (row: UploadSummary) => <StatusBadge status={row.status} /> },
    { key: "total_rows", label: "Total", className: "text-right" },
    { key: "accepted_count", label: "Accepted", className: "text-right" },
    { key: "failed_count", label: "Failed", className: "text-right" },
    { key: "uploaded_at", label: "Uploaded", render: (row: UploadSummary) => row.uploaded_at || "-", className: "text-slate-500" },
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
        {/* Status filter tabs */}
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

        {/* Search fields */}
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

      {/* Tabs */}
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
    </div>
  );
}
