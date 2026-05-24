import { useState } from "react";
import { Link } from "react-router-dom";
import type { PendingSAR } from "../types";
import StatusBadge from "./StatusBadge";

interface ReviewCardProps {
  sar: PendingSAR;
  onReview: (action: string) => Promise<void>;
  reviewing: boolean;
}

export default function ReviewCard({ sar, onReview, reviewing }: ReviewCardProps) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="bg-white border border-slate-200 rounded-lg overflow-hidden">
      {/* Transaction Header - always visible */}
      <div className="px-5 py-4 flex items-start justify-between cursor-pointer" onClick={() => setExpanded(!expanded)}>
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1 flex-wrap">
            {sar.source_txn_id ? (
              <Link to={`/transactions?source_txn_id=${encodeURIComponent(sar.source_txn_id)}`}
                className="font-mono text-sm text-blue-600 hover:text-blue-800 hover:underline">
                {sar.source_txn_id}
              </Link>
            ) : (
              <span className="font-mono text-sm text-slate-500">—</span>
            )}
            <StatusBadge status={sar.sar_status} />
            {sar.risk_level && (
              <span className={`inline-flex items-center px-2 py-0.5 text-xs font-medium rounded-full ${
                sar.risk_level === "high" ? "bg-red-100 text-red-700" :
                sar.risk_level === "medium" ? "bg-amber-100 text-amber-700" :
                "bg-green-100 text-green-700"
              }`}>
                {sar.risk_level}
              </span>
            )}
            {sar.customer_id && (
              <Link to={`/compliance?customer_id=${encodeURIComponent(sar.customer_id)}`}
                className="font-mono text-xs text-blue-600 hover:text-blue-800 hover:underline shrink-0 inline-flex items-center gap-1">
                {sar.customer_first_name && sar.customer_last_name
                  ? `${sar.customer_first_name} ${sar.customer_last_name}`
                  : sar.customer_id}
                <svg className="w-3 h-3 text-slate-400" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="6.5" cy="6.5" r="4.5" />
                  <line x1="10" y1="10" x2="14" y2="14" />
                </svg>
              </Link>
            )}
          </div>
          <div className="flex flex-wrap gap-x-6 gap-y-1 text-sm">
            <span className="text-slate-700 font-medium">${sar.amount?.toLocaleString() ?? "—"}</span>
            <span className="text-slate-500">{sar.counterparty}</span>
            <span className="text-slate-500">{[sar.city, sar.state, sar.country].filter(Boolean).join(", ") || "—"}</span>
            <span className="text-slate-500">{sar.date || "—"}</span>
            {sar.account_id && (
              <Link to={`/transactions?account_id=${encodeURIComponent(sar.account_id)}`}
                className="font-mono text-blue-600 hover:text-blue-800 hover:underline">
                {sar.account_id}
              </Link>
            )}
          </div>
          {sar.rule_name && (
            <div className="mt-1.5 text-xs text-slate-400">
              Rule: {sar.rule_name}
            </div>
          )}
        </div>
        <div className="text-slate-400 text-lg ml-4">{expanded ? "▲" : "▼"}</div>
      </div>

      {/* Expanded Detail */}
      {expanded && (
        <div className="px-5 py-4 border-t border-slate-100 space-y-4">
          {/* Rules triggered */}
          {sar.flag_details && Object.keys(sar.flag_details).length > 0 && (
            <div>
              <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Rules Triggered</h4>
              <div className="space-y-1">
                {Object.entries(sar.flag_details).map(([id, name]) => (
                  <div key={id} className="text-sm text-slate-700 flex items-center gap-2">
                    <span className="w-1.5 h-1.5 rounded-full bg-red-400" />
                    {name}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Enriched Context */}
          {(() => {
            const e = sar.enrichment as Record<string, unknown> | null;
            if (!e) return null;
            return (
              <div>
                <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Enriched Context</h4>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                  {e.customer_txn_count_30d !== undefined && (
                    <div className="bg-slate-50 rounded p-2.5">
                      <div className="text-lg font-semibold text-slate-800">{e.customer_txn_count_30d as number}</div>
                      <div className="text-xs text-slate-500">30d Txn Count</div>
                    </div>
                  )}
                  {e.customer_avg_30d !== undefined && (
                    <div className="bg-slate-50 rounded p-2.5">
                      <div className="text-lg font-semibold text-slate-800">${(e.customer_avg_30d as number).toLocaleString()}</div>
                      <div className="text-xs text-slate-500">30d Avg Amount</div>
                    </div>
                  )}
                  {e.structuring_24h_count !== undefined && (
                    <div className="bg-slate-50 rounded p-2.5">
                      <div className="text-lg font-semibold text-slate-800">{e.structuring_24h_count as number}</div>
                      <div className="text-xs text-slate-500">Structuring Alerts</div>
                    </div>
                  )}
                  {e.velocity_zscore !== undefined && e.velocity_zscore !== null && (
                    <div className="bg-slate-50 rounded p-2.5">
                      <div className={`text-lg font-semibold ${(e.velocity_zscore as number) > 2 ? "text-red-600" : "text-slate-800"}`}>
                        {(e.velocity_zscore as number).toFixed(2)}
                      </div>
                      <div className="text-xs text-slate-500">Velocity Z-Score</div>
                    </div>
                  )}
                  {e.dormancy_days !== undefined && e.dormancy_days !== null && (
                    <div className="bg-slate-50 rounded p-2.5">
                      <div className="text-lg font-semibold text-slate-800">{e.dormancy_days as number}d</div>
                      <div className="text-xs text-slate-500">Dormancy</div>
                    </div>
                  )}
                  {!!e.account_type && (
                    <div className="bg-slate-50 rounded p-2.5">
                      <div className="text-lg font-semibold text-slate-800">{String(e.account_type)}</div>
                      <div className="text-xs text-slate-500">Account Type</div>
                    </div>
                  )}
                </div>
              </div>
            );
          })()}

          {/* Transaction Links */}
          <div className="flex flex-wrap gap-x-6 gap-y-1 text-sm">
            {sar.source_txn_id && (
              <Link to={`/transactions?source_txn_id=${encodeURIComponent(sar.source_txn_id)}`}
                className="text-blue-600 hover:text-blue-800 hover:underline">
                Txn: {sar.source_txn_id}
              </Link>
            )}
            {sar.account_id && (
              <Link to={`/transactions?account_id=${encodeURIComponent(sar.account_id)}`}
                className="text-blue-600 hover:text-blue-800 hover:underline">
                Acct: {sar.account_id}
              </Link>
            )}
            {sar.customer_id && (
              <Link to={`/compliance?customer_id=${encodeURIComponent(sar.customer_id)}`}
                className="text-blue-600 hover:text-blue-800 hover:underline inline-flex items-center gap-1">
                Cust: {sar.customer_first_name && sar.customer_last_name
                  ? `${sar.customer_first_name} ${sar.customer_last_name}`
                  : sar.customer_id}
                <svg className="w-3 h-3 text-slate-400" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="6.5" cy="6.5" r="4.5" />
                  <line x1="10" y1="10" x2="14" y2="14" />
                </svg>
              </Link>
            )}
          </div>

          {/* SAR Narrative */}
          <div>
            <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">SAR Report</h4>
            <div className="bg-slate-50 rounded-lg p-4 text-sm text-slate-700 whitespace-pre-wrap leading-relaxed">
              {sar.sar_content}
            </div>
          </div>
        </div>
      )}

      {/* Action Buttons */}
      <div className="px-5 py-3 border-t border-slate-100 bg-slate-50 flex justify-end gap-3">
        <button
          onClick={() => onReview("dismissed")}
          disabled={reviewing}
          className="px-4 py-2 text-sm font-medium rounded-lg border border-slate-300 text-slate-700 hover:bg-slate-100 disabled:opacity-40 transition-colors"
        >
          {reviewing ? "..." : "Dismiss"}
        </button>
        <button
          onClick={() => onReview("confirmed")}
          disabled={reviewing}
          className="px-4 py-2 text-sm font-medium rounded-lg bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-40 transition-colors"
        >
          {reviewing ? "..." : "Confirm"}
        </button>
      </div>
    </div>
  );
}
