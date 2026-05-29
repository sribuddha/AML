import { useState, useMemo } from "react";
import type { ReactNode } from "react";
import Pagination from "./Pagination";

export interface Column<T> {
  key: string;
  label: string;
  sortable?: boolean;
  render?: (item: T) => ReactNode;
  className?: string;
}

interface DataTableProps<T> {
  columns: Column<T>[];
  data: T[];
  loading?: boolean;
  emptyMessage?: string;
  error?: string | null;
  onRetry?: () => void;
  page?: number;
  perPage?: number;
  total?: number;
  onPageChange?: (page: number) => void;
  onSort?: (key: string, dir: "asc" | "desc") => void;
  sortBy?: string | null;
  sortDir?: "asc" | "desc" | null;
}

function compareValue(a: unknown, b: unknown): number {
  if (a == null && b == null) return 0;
  if (a == null) return 1;
  if (b == null) return -1;
  if (typeof a === "number" && typeof b === "number") return a - b;
  const na = Number(a);
  const nb = Number(b);
  if (!Number.isNaN(na) && !Number.isNaN(nb)) return na - nb;
  return String(a).localeCompare(String(b));
}

function sortData<T>(data: T[], key: string, dir: "asc" | "desc"): T[] {
  return [...data].sort((a, b) => {
    const aVal = (a as Record<string, unknown>)[key];
    const bVal = (b as Record<string, unknown>)[key];
    const cmp = compareValue(aVal, bVal);
    return dir === "asc" ? cmp : -cmp;
  });
}

function SkeletonRow({ cols }: { cols: number }) {
  return (
    <tr>
      {Array.from({ length: cols }).map((_, i) => (
        <td key={i} className="px-4 py-3">
          <div className="h-4 bg-slate-200 rounded animate-pulse" style={{ width: `${60 + Math.random() * 40}%` }} />
        </td>
      ))}
    </tr>
  );
}

function renderBody<T>(columns: Column<T>[], _data: T[], loading: boolean | undefined, emptyMessage: string, error: string | null | undefined, onRetry: (() => void) | undefined) {
  if (loading) {
    return Array.from({ length: 5 }).map((_, i) => <SkeletonRow key={i} cols={columns.length} />);
  }
  if (error) {
    return (
      <tr>
        <td colSpan={columns.length} className="px-4 py-8 text-center">
          <div className="text-red-500 text-sm mb-2">{error}</div>
          {onRetry && (
            <button onClick={onRetry} className="text-blue-600 hover:text-blue-800 text-sm font-medium">Retry</button>
          )}
        </td>
      </tr>
    );
  }
  if (_data.length === 0) {
    return (
      <tr>
        <td colSpan={columns.length} className="px-4 py-8 text-center text-slate-400 text-sm">{emptyMessage}</td>
      </tr>
    );
  }
  return _data.map((item, i) => {
    const row = item as Record<string, unknown>;
    return (
      <tr key={String(row.id ?? i)} className="hover:bg-slate-50 even:bg-slate-50/50">
        {columns.map((col) => {
          const val = col.render ? col.render(item) : String(row[col.key] ?? "-");
          return <td key={col.key} className={`px-4 py-3 text-sm text-slate-700 ${col.className || ""}`}>{val}</td>;
        })}
      </tr>
    );
  });
}

export default function DataTable<T = any>({
  columns, data, loading, emptyMessage = "No data found", error, onRetry,
  page, perPage, total, onPageChange,
  onSort, sortBy: externalSortBy, sortDir: externalSortDir,
}: DataTableProps<T>) {
  const isServerSort = onSort !== undefined;
  const [localSortBy, setLocalSortBy] = useState<string | null>(null);
  const [localSortDir, setLocalSortDir] = useState<"asc" | "desc" | null>(null);

  const sortBy = isServerSort ? (externalSortBy ?? null) : localSortBy;
  const sortDir = isServerSort ? (externalSortDir ?? null) : localSortDir;

  const displayed = useMemo(() => {
    if (!sortBy || !sortDir) return data;
    if (isServerSort) return data;
    return sortData(data, sortBy, sortDir);
  }, [data, sortBy, sortDir, isServerSort]);

  const handleSort = (key: string) => {
    if (isServerSort) {
      if (externalSortBy !== key) {
        onSort(key, "asc");
      } else if (externalSortDir === "asc") {
        onSort(key, "desc");
      } else if (externalSortDir === "desc") {
        onSort(key, "asc");
      }
      return;
    }
    if (localSortBy !== key) {
      setLocalSortBy(key);
      setLocalSortDir("asc");
    } else if (localSortDir === "asc") {
      setLocalSortDir("desc");
    } else if (localSortDir === "desc") {
      setLocalSortBy(null);
      setLocalSortDir(null);
    }
  };

  return (
    <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="bg-slate-50 border-b border-slate-200">
              {columns.map((col) => {
                const sortable = col.sortable !== false;
                return (
                  <th
                    key={col.key}
                    className={`px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider ${
                      sortable ? "cursor-pointer select-none hover:text-slate-700" : ""
                    } ${col.className || ""}`}
                    onClick={() => sortable && handleSort(col.key)}
                  >
                    <span className="inline-flex items-center gap-1">
                      {col.label}
                      {sortable && sortBy === col.key && (
                        <span className="text-blue-500">{sortDir === "asc" ? "▲" : "▼"}</span>
                      )}
                    </span>
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {renderBody(columns, displayed, loading, emptyMessage, error, onRetry)}
          </tbody>
        </table>
      </div>
      {total !== undefined && total > 0 && onPageChange && (
        <div className="border-t border-slate-200">
          <Pagination page={page || 1} perPage={perPage || 50} total={total} onPageChange={onPageChange} />
        </div>
      )}
    </div>
  );
}
