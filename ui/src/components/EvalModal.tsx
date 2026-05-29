import { useState, useEffect } from "react"
import { api } from "../api/client"
import type { EvalReport } from "../types"

interface EvalModalProps {
  uploadId: string
  open: boolean
  onClose: () => void
  fetchReport?: (uploadId: string) => Promise<EvalReport>
}

function pct(v: number) {
  return `${(v * 100).toFixed(1)}%`
}

function colorClass(v: number) {
  return v >= 0.8 ? "text-green-600" : v >= 0.5 ? "text-amber-600" : "text-red-600"
}

export default function EvalModal({ uploadId, open, onClose, fetchReport }: EvalModalProps) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [report, setReport] = useState<EvalReport | null>(null)

  useEffect(() => {
    if (!open) return
    setLoading(true)
    setError(null)
    setReport(null)

    const load = fetchReport
      ? fetchReport(uploadId)
      : api.post<EvalReport>(`/api/uploads/${uploadId}/eval`)

    load
      .then(setReport)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Eval failed"))
      .finally(() => setLoading(false))
  }, [uploadId, open, fetchReport])

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onClose}>
      <div
        className="bg-white rounded-lg shadow-xl max-w-3xl w-full max-h-[85vh] overflow-auto mx-4"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200">
          <h3 className="text-lg font-semibold text-slate-800">Eval Report</h3>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 text-xl leading-none">&times;</button>
        </div>

        {/* Body */}
        <div className="p-6 space-y-6">
          {loading && (
            <div className="flex items-center gap-3 text-sm text-slate-500">
              <div className="w-4 h-4 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
              Running evaluation...
            </div>
          )}

          {error && (
            <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-sm text-red-700">{error}</div>
          )}

          {report && (
            <>
              {/* Summary cards */}
              <div className="grid grid-cols-3 gap-4">
                <div className="bg-slate-50 rounded-lg p-3 text-center">
                  <div className="text-2xl font-bold text-slate-800">{report.total_transactions}</div>
                  <div className="text-xs text-slate-500">Transactions</div>
                </div>
                <div className="bg-slate-50 rounded-lg p-3 text-center">
                  <div className="text-2xl font-bold text-red-600">{report.total_anomalous}</div>
                  <div className="text-xs text-slate-500">Anomalous (expected)</div>
                </div>
                <div className="bg-slate-50 rounded-lg p-3 text-center">
                  <div className="text-2xl font-bold text-amber-600">{report.total_flagged}</div>
                  <div className="text-xs text-slate-500">Flagged (actual)</div>
                </div>
              </div>

              {/* Overall metrics */}
              <div className="grid grid-cols-3 gap-4">
                <div className="bg-indigo-50 rounded-lg p-3 text-center">
                  <div className="text-2xl font-bold text-indigo-700">{pct(report.overall_precision)}</div>
                  <div className="text-xs text-indigo-500">Precision</div>
                </div>
                <div className="bg-indigo-50 rounded-lg p-3 text-center">
                  <div className="text-2xl font-bold text-indigo-700">{pct(report.overall_recall)}</div>
                  <div className="text-xs text-indigo-500">Recall</div>
                </div>
                <div className="bg-indigo-50 rounded-lg p-3 text-center">
                  <div className="text-2xl font-bold text-indigo-700">{pct(report.overall_f1)}</div>
                  <div className="text-xs text-indigo-500">F1 Score</div>
                </div>
              </div>

              {/* Hallucination + Completeness */}
              <div className="grid grid-cols-2 gap-4">
                <div className="bg-teal-50 rounded-lg p-3 text-center">
                  <div className="text-2xl font-bold text-teal-700">{pct(report.hallucination_free_rate)}</div>
                  <div className="text-xs text-teal-500">Hallucination-Free</div>
                </div>
                <div className="bg-teal-50 rounded-lg p-3 text-center">
                  <div className="text-2xl font-bold text-teal-700">{pct(report.avg_completeness)}</div>
                  <div className="text-xs text-teal-500">Avg Completeness</div>
                </div>
              </div>

              {/* Pattern metrics table */}
              {report.pattern_metrics.length > 0 && (
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
                        {report.pattern_metrics.map((pm, i) => (
                          <tr key={i} className={i % 2 === 0 ? "bg-white" : "bg-slate-50/50"}>
                            <td className="px-3 py-1.5 text-slate-700 border-b border-slate-100">{pm.pattern}</td>
                            <td className="px-3 py-1.5 text-right text-slate-700 border-b border-slate-100">{pm.total}</td>
                            <td className="px-3 py-1.5 text-right text-slate-700 border-b border-slate-100">{pm.flagged}</td>
                            <td className={`px-3 py-1.5 text-right border-b border-slate-100 ${colorClass(pm.precision)}`}>
                              {pct(pm.precision)}
                            </td>
                            <td className={`px-3 py-1.5 text-right border-b border-slate-100 ${colorClass(pm.recall)}`}>
                              {pct(pm.recall)}
                            </td>
                            <td className={`px-3 py-1.5 text-right border-b border-slate-100 ${colorClass(pm.f1)}`}>
                              {pct(pm.f1)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* Hallucination results */}
              {report.hallucination_results.filter((h) => !h.passed).length > 0 && (
                <div>
                  <h4 className="text-sm font-semibold text-slate-500 uppercase tracking-wider mb-2">Hallucination Issues</h4>
                  <div className="space-y-2">
                    {report.hallucination_results.filter((h) => !h.passed).map((h) => (
                      <div key={h.sar_id} className="bg-red-50 border border-red-200 rounded-lg px-3 py-2">
                        <div className="text-xs font-mono text-red-700">SAR {h.sar_id.substring(0, 8)}...</div>
                        <div className="text-xs text-red-600 mt-1">Hallucinated facts: {h.hallucinated_facts.join(", ")}</div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Completeness issues */}
              {report.completeness_results.filter((c) => c.score < 1).length > 0 && (
                <div>
                  <h4 className="text-sm font-semibold text-slate-500 uppercase tracking-wider mb-2">Completeness Issues</h4>
                  <div className="space-y-2">
                    {report.completeness_results.filter((c) => c.score < 1).map((c) => (
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
  )
}
