import { useState, useEffect, useCallback } from "react";
import { api } from "../api/client";
import DataTable from "../components/DataTable";
import type { RuleResponse, RuleCreate, PaginatedResponse } from "../types";

type RuleAction = "create" | "edit" | null;

const EMPTY_RULE: RuleCreate = {
  name: "",
  description: "",
  type: "deterministic",
  status: "active",
  rules_json: [],
};

export default function RulesPage() {
  const [rules, setRules] = useState<PaginatedResponse<RuleResponse> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);

  const [typeFilter, setTypeFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [nameFilter, setNameFilter] = useState("");

  const [action, setAction] = useState<RuleAction>(null);
  const [editId, setEditId] = useState<string | null>(null);
  const [form, setForm] = useState<RuleCreate>(EMPTY_RULE);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const fetchRules = useCallback(async (p: number) => {
    setLoading(true);
    setError(null);
    try {
      const result = await api.get<PaginatedResponse<RuleResponse>>("/api/rules", {
        type: typeFilter || undefined,
        status: statusFilter.toLowerCase() === "all" ? "all" : (statusFilter || undefined),
        name: nameFilter || undefined,
        page: p, per_page: 25,
      });
      setRules(result);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, [typeFilter, statusFilter, nameFilter]);

  useEffect(() => { fetchRules(page); }, [page, fetchRules]);

  const handleSearch = () => { setPage(1); fetchRules(1); };

  const openCreate = () => {
    setEditId(null);
    setForm({ ...EMPTY_RULE });
    setFormError(null);
    setAction("create");
  };

  const openEdit = (rule: RuleResponse) => {
    setEditId(rule.id);
    setForm({ name: rule.name, description: rule.description, type: rule.type, status: rule.status, rules_json: rule.rules_json });
    setFormError(null);
    setAction("edit");
  };

  const closeForm = () => {
    setAction(null);
    setEditId(null);
    setFormError(null);
  };

  const handleSave = async () => {
    if (!form.name.trim()) {
      setFormError("Name is required");
      return;
    }
    setSaving(true);
    setFormError(null);
    try {
      if (action === "create") {
        await api.post<RuleResponse>("/api/rules", form);
      } else if (editId) {
        await api.put<RuleResponse>(`/api/rules/${editId}`, form);
      }
      closeForm();
      await fetchRules(page);
    } catch (e: unknown) {
      setFormError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  };

  const handleToggleStatus = async (rule: RuleResponse) => {
    const newStatus = rule.status === "active" ? "inactive" : "active";
    const label = newStatus === "inactive" ? "deactivate" : "reactivate";
    if (!window.confirm(`${label.charAt(0).toUpperCase() + label.slice(1)} rule "${rule.name}"?`)) return;
    try {
      await api.patch<RuleResponse>(`/api/rules/${rule.id}/status`, { status: newStatus });
      await fetchRules(page);
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : "Failed to update status");
    }
  };

  const columns = [
    { key: "name", label: "Name", render: (row: RuleResponse) =>
        <button onClick={() => openEdit(row)} className="text-blue-600 hover:text-blue-800 hover:underline font-medium text-sm">
          {row.name}
        </button>,
    },
    { key: "type", label: "Type", render: (row: RuleResponse) => <span className="text-xs font-mono text-slate-500">{row.type}</span> },
    { key: "status", label: "Status", render: (row: RuleResponse) => {
        const colors: Record<string, string> = { active: "bg-green-100 text-green-700", inactive: "bg-slate-100 text-slate-500" };
        return <span className={`inline-block px-2 py-0.5 text-xs font-medium rounded-full ${colors[row.status] || "bg-slate-100 text-slate-600"}`}>{row.status}</span>;
      },
    },
    { key: "description", label: "Description", render: (row: RuleResponse) => row.description || "-", className: "text-slate-500" },
    { key: "actions", label: "", sortable: false, render: (row: RuleResponse) =>
        <button onClick={() => handleToggleStatus(row)}
          className={`text-xs font-medium hover:underline ${row.status === "active" ? "text-amber-600 hover:text-amber-800" : "text-green-600 hover:text-green-800"}`}>
          {row.status === "active" ? "Deactivate" : "Activate"}
        </button>,
      className: "text-right",
    },
  ];

  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-lg font-semibold text-slate-800">Rules</h3>
        <p className="text-sm text-slate-500 mt-0.5">Manage AML detection rules</p>
      </div>

      {/* Filters + Add */}
      <div className="bg-white border border-slate-200 rounded-lg p-4 space-y-3">
        <div className="flex gap-3 items-end flex-wrap">
          <div>
            <label className="text-xs text-slate-500 mb-0.5 block">Type</label>
            <input placeholder="Filter by type" value={typeFilter} onChange={e => setTypeFilter(e.target.value)}
              className="px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
          </div>
          <div>
            <label className="text-xs text-slate-500 mb-0.5 block">Status</label>
            <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)}
              className="px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white">
              <option value="">All</option>
              <option value="active">Active</option>
              <option value="inactive">Inactive</option>
            </select>
          </div>
          <div>
            <label className="text-xs text-slate-500 mb-0.5 block">Name</label>
            <input placeholder="Filter by name" value={nameFilter} onChange={e => setNameFilter(e.target.value)}
              className="px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
          </div>
          <button onClick={handleSearch}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors">
            Search
          </button>
          <button onClick={openCreate}
            className="px-4 py-2 bg-green-600 text-white rounded-lg text-sm font-medium hover:bg-green-700 transition-colors ml-auto">
            + Add Rule
          </button>
        </div>
      </div>

      {/* Create/Edit form */}
      {action && (
        <div className="bg-white border border-blue-200 rounded-lg p-5 space-y-3">
          <h4 className="text-sm font-semibold text-slate-700">{action === "create" ? "Add Rule" : "Edit Rule"}</h4>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-slate-500 mb-0.5 block">Name</label>
              <input value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
            </div>
            <div>
              <label className="text-xs text-slate-500 mb-0.5 block">Type</label>
              <select value={form.type} onChange={e => setForm(f => ({ ...f, type: e.target.value }))}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white">
                <option value="deterministic">deterministic</option>
              </select>
            </div>
            <div>
              <label className="text-xs text-slate-500 mb-0.5 block">Status</label>
              <select value={form.status} onChange={e => setForm(f => ({ ...f, status: e.target.value }))}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white">
                <option value="active">active</option>
                <option value="inactive">inactive</option>
              </select>
            </div>
            <div className="col-span-2">
              <label className="text-xs text-slate-500 mb-0.5 block">Description</label>
              <input value={form.description || ""} onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
            </div>
            <div className="col-span-2">
              <label className="text-xs text-slate-500 mb-0.5 block">Rules JSON</label>
              <textarea value={JSON.stringify(form.rules_json, null, 2)}
                onChange={e => { try { setForm(f => ({ ...f, rules_json: JSON.parse(e.target.value) })); } catch {} }}
                rows={6}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500" />
              <p className="text-xs text-slate-400 mt-1">JSON array of rule conditions/actions</p>
            </div>
          </div>

          {formError && <p className="text-sm text-red-600">{formError}</p>}

          <div className="flex gap-2">
            <button onClick={handleSave} disabled={saving}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-60 transition-colors">
              {saving ? "Saving..." : "Save"}
            </button>
            <button onClick={closeForm}
              className="px-4 py-2 border border-slate-300 text-slate-700 rounded-lg text-sm font-medium hover:bg-slate-50 transition-colors">
              Cancel
            </button>
          </div>
        </div>
      )}

      <DataTable
        columns={columns}
        data={rules?.items || []}
        loading={loading}
        error={error}
        onRetry={() => fetchRules(page)}
        emptyMessage="No rules found."
        page={rules?.page}
        perPage={rules?.per_page}
        total={rules?.total}
        onPageChange={(p) => setPage(p)}
      />
    </div>
  );
}
