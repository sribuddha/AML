import { useState, useCallback, useEffect, useRef } from "react"
import { useNavigate, useSearchParams } from "react-router-dom"
import { api } from "../api/client"
import { toast } from "../lib/toast"
import DataTable from "../components/DataTable"
import StatusBadge from "../components/StatusBadge"
import FileUploader from "../components/FileUploader"
import PageShell from "../components/PageShell"
import TabSet from "../components/TabSet"
import SearchForm from "../components/SearchForm"
import EvalModal from "../components/EvalModal"
import type { UploadSummary, PaginatedResponse } from "../types"

const STATUS_TABS = ["All", "Uploaded", "Processing", "Pending Review", "Complete", "Failed"]

export default function OperationsPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const initialTabIsUpload = useRef(searchParams.get("tab") === "upload")
  const [activeTab, setActiveTab] = useState<"upload" | "search">(
    initialTabIsUpload.current ? "upload" : "search",
  )

  const [uploadId, setUploadId] = useState("")
  const [statusTab, setStatusTab] = useState("All")
  const [fromDate, setFromDate] = useState("")
  const [toDate, setToDate] = useState("")
  const [data, setData] = useState<PaginatedResponse<UploadSummary> | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [page, setPage] = useState(1)
  const [uploadResult, setUploadResult] = useState<{
    total_rows: number
    accepted_count: number
    failed_count: number
  } | null>(null)
  const [searched, setSearched] = useState(false)

  const [evalUploadId, setEvalUploadId] = useState<string | null>(null)

  const fetchUploads = useCallback(async (p: number) => {
    setLoading(true)
    setError(null)
    setSearched(true)
    try {
      const result = await api.get<PaginatedResponse<UploadSummary>>("/api/uploads/search", {
        upload_id: uploadId || undefined,
        status: statusTab === "All" ? undefined : statusTab.toLowerCase().replace(" ", "_"),
        from_date: fromDate || undefined,
        to_date: toDate || undefined,
        page: p, per_page: 25,
      })
      setData(result)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load")
    } finally {
      setLoading(false)
    }
  }, [uploadId, statusTab, fromDate, toDate])

  const handleSearch = () => { setPage(1); fetchUploads(1) }

  useEffect(() => {
    if (!initialTabIsUpload.current) {
      fetchUploads(1)
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const handleUpload = async (file: File) => {
    try {
      const result = await api.upload<{ total_rows: number; accepted_count: number; failed_count: number }>("/api/uploads", file)
      setUploadResult(result)
      toast.success(`Uploaded ${result.accepted_count} rows`)
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Upload failed")
    }
  }

  const uploadColumns = [
    {
      key: "id", label: "Upload ID", sortable: false,
      render: (row: UploadSummary) =>
        row.status === "pending_human" ? (
          <button onClick={() => navigate(`/compliance?upload_id=${row.id}`)}
            className="text-blue-600 hover:text-blue-800 hover:underline font-mono text-[10px]">
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
    {
      key: "uploaded_at", label: "Uploaded",
      render: (row: UploadSummary) =>
        row.uploaded_at ? row.uploaded_at.replace(/\.\d+/, "").replace(/Z$/, "") : "-",
      className: "text-slate-500",
    },
    {
      key: "pending_sar_count", label: "Pending", sortable: false,
      render: (row: UploadSummary) =>
        row.status === "pending_human" ? (
          <span className="inline-flex items-center justify-center min-w-[22px] h-5 px-1.5 bg-amber-100 text-amber-700 text-xs font-bold rounded-full">
            {row.pending_sar_count}
          </span>
        ) : (
          <span className="text-slate-300">-</span>
        ),
    },
    {
      key: "eval", label: "Eval", sortable: false,
      render: (row: UploadSummary) =>
        row.eval_file && row.status === "complete" ? (
          <button onClick={() => setEvalUploadId(row.id)}
            className="px-2 py-1 text-xs font-medium bg-indigo-50 text-indigo-600 border border-indigo-200 rounded hover:bg-indigo-100 transition-colors">
            Eval
          </button>
        ) : null,
    },
  ]

  const searchFields = [
    { key: "uploadId", label: "Upload ID", placeholder: "Upload ID" },
    { key: "fromDate", label: "From", type: "date" as const },
    { key: "toDate", label: "To", type: "date" as const },
  ]

  const searchValues = { uploadId, fromDate, toDate }

  const handleSearchChange = (key: string, value: string) => {
    if (key === "uploadId") setUploadId(value)
    else if (key === "fromDate") setFromDate(value)
    else if (key === "toDate") setToDate(value)
  }

  return (
    <PageShell title="Operations" description="Upload files and manage uploads">
      <TabSet
        tabs={[
          { id: "search", label: "Search Uploads" },
          { id: "upload", label: "Upload" },
        ]}
        active={activeTab}
        onChange={(id) => setActiveTab(id as "upload" | "search")}
      />

      {activeTab === "upload" ? (
        <div className="space-y-4">
          <FileUploader onUpload={handleUpload} />
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
              <button onClick={() => { setActiveTab("search"); setPage(1); }}
                className="mt-4 text-sm text-blue-600 hover:text-blue-800 hover:underline">
                View Uploads &rarr;
              </button>
            </div>
          )}
        </div>
      ) : (
        <div className="space-y-4">
          {/* Status filter pills */}
          <div className="flex flex-wrap gap-1">
            {STATUS_TABS.map((s) => (
              <button key={s} onClick={() => { setStatusTab(s); setPage(1) }}
                className={`px-3 py-1.5 text-xs font-medium rounded-full transition-colors ${
                  statusTab === s
                    ? "bg-blue-600 text-white"
                    : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                }`}>
                {s}
              </button>
            ))}
          </div>

          <SearchForm
            fields={searchFields}
            values={searchValues}
            onChange={handleSearchChange}
            onSearch={handleSearch}
          />

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
      )}

      <EvalModal
        uploadId={evalUploadId || ""}
        open={evalUploadId !== null}
        onClose={() => setEvalUploadId(null)}
      />
    </PageShell>
  )
}
