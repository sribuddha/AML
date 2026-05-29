import { useState, useEffect } from "react"
import { api } from "../api/client"
import { toast } from "../lib/toast"
import DataTable from "../components/DataTable"
import PageShell from "../components/PageShell"
import SearchForm from "../components/SearchForm"
import ConfirmDialog from "../components/ConfirmDialog"
import type { RuleResponse, RuleCreate, PaginatedResponse } from "../types"

const EMPTY_RULE: RuleCreate = {
  name: "", description: "", type: "deterministic", status: "active", rules_json: [],
}

type RuleAction = "create" | "edit" | null

export default function RulesPage() {
  const [rules, setRules] = useState<RuleResponse[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [filters, setFilters] = useState<Record<string, string>>({
    nameFilter: "", typeFilter: "", statusFilter: "",
  })
  const [formData, setFormData] = useState<RuleCreate>(EMPTY_RULE)
  const [action, setAction] = useState<RuleAction>(null)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [formError, setFormError] = useState<string | null>(null)

  const [confirmAction, setConfirmAction] = useState<{ ruleId: string; name: string; newStatus: string } | null>(null)

  const fetchRules = async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await api.get<PaginatedResponse<RuleResponse>>("/api/rules", { per_page: 100 })
      setRules(result.items)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchRules() }, [])

  const filtered = rules.filter((r) => {
    if (filters.nameFilter && !r.name.toLowerCase().includes(filters.nameFilter.toLowerCase())) return false
    if (filters.typeFilter && filters.typeFilter !== "all" && r.type !== filters.typeFilter) return false
    if (filters.statusFilter && filters.statusFilter !== "all" && r.status !== filters.statusFilter) return false
    return true
  })

  const handleFilterChange = (key: string, value: string) => {
    setFilters((prev) => ({ ...prev, [key]: value }))
  }

  const startCreate = () => {
    setFormData(EMPTY_RULE)
    setEditingId(null)
    setFormError(null)
    setAction("create")
  }

  const startEdit = (rule: RuleResponse) => {
    setFormData({
      name: rule.name,
      description: rule.description || "",
      type: rule.type,
      status: rule.status,
      rules_json: rule.rules_json,
    })
    setEditingId(rule.id)
    setFormError(null)
    setAction("edit")
  }

  const cancelForm = () => {
    setAction(null)
    setEditingId(null)
    setFormError(null)
  }

  const handleSave = async () => {
    if (!formData.name.trim()) {
      setFormError("Name is required")
      return
    }
    setFormError(null)
    try {
      if (action === "create") {
        await api.post("/api/rules", formData)
        toast.success("Rule created")
      } else if (editingId) {
        await api.patch(`/api/rules/${editingId}`, formData)
        toast.success("Rule updated")
      }
      cancelForm()
      await fetchRules()
    } catch (e: unknown) {
      setFormError(e instanceof Error ? e.message : "Save failed")
    }
  }

  const handleToggleStatus = async () => {
    if (!confirmAction) return
    try {
      await api.patch(`/api/rules/${confirmAction.ruleId}/status`, { status: confirmAction.newStatus })
      toast.success(`Rule ${confirmAction.newStatus === "active" ? "activated" : "deactivated"}`)
      setConfirmAction(null)
      await fetchRules()
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Failed to update status")
      setConfirmAction(null)
    }
  }

  const searchFields = [
    { key: "nameFilter", label: "Name", placeholder: "Filter by name..." },
    {
      key: "typeFilter", label: "Type", type: "select" as const,
      options: [
        { label: "All Types", value: "all" },
        { label: "Deterministic", value: "deterministic" },
      ],
    },
    {
      key: "statusFilter", label: "Status", type: "select" as const,
      options: [
        { label: "All Statuses", value: "all" },
        { label: "Active", value: "active" },
        { label: "Inactive", value: "inactive" },
      ],
    },
  ]

  const ruleColumns = [
    { key: "name", label: "Name", sortable: true },
    { key: "type", label: "Type", sortable: true },
    { key: "status", label: "Status", sortable: true },
    {
      key: "rules_json", label: "Conditions", sortable: false,
      render: (row: RuleResponse) => (
        <span className="font-mono text-xs text-slate-500">
          {Array.isArray(row.rules_json) ? row.rules_json.length : 0} conditions
        </span>
      ),
    },
    {
      key: "actions", label: "Actions", sortable: false,
      render: (row: RuleResponse) => (
        <div className="flex gap-1">
          <button onClick={() => startEdit(row)}
            className="px-2 py-1 text-xs font-medium text-blue-600 hover:bg-blue-50 rounded transition-colors">
            Edit
          </button>
          <button onClick={() => setConfirmAction({
            ruleId: row.id, name: row.name,
            newStatus: row.status === "active" ? "inactive" : "active",
          })}
            className="px-2 py-1 text-xs font-medium text-red-600 hover:bg-red-50 rounded transition-colors">
            {row.status === "active" ? "Deactivate" : "Activate"}
          </button>
        </div>
      ),
    },
  ]

  return (
    <PageShell
      title="Rules"
      description="Manage AML detection rules"
      actions={
        action === null && (
          <button onClick={startCreate}
            className="px-4 py-2 text-sm font-medium rounded-lg bg-blue-600 text-white hover:bg-blue-700 transition-colors">
            + New Rule
          </button>
        )
      }
    >
      <SearchForm
        fields={searchFields}
        values={filters}
        onChange={handleFilterChange}
        onSearch={() => {}}
      />

      {/* Create/Edit form */}
      {action && (
        <div className="bg-white border border-slate-200 rounded-lg p-5 space-y-4">
          <h3 className="text-sm font-semibold text-slate-500 uppercase tracking-wider">
            {action === "create" ? "New Rule" : "Edit Rule"}
          </h3>
          {formError && (
            <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-sm text-red-700">{formError}</div>
          )}
          <div className="grid grid-cols-2 gap-4">
            <div className="col-span-2 sm:col-span-1">
              <label className="block text-xs font-medium text-slate-500 mb-1">Name</label>
              <input value={formData.name}
                onChange={(e) => setFormData((p) => ({ ...p, name: e.target.value }))}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500" />
            </div>
            <div className="col-span-2 sm:col-span-1">
              <label className="block text-xs font-medium text-slate-500 mb-1">Type</label>
              <select value={formData.type}
                onChange={(e) => setFormData((p) => ({ ...p, type: e.target.value }))}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500">
                <option value="deterministic">Deterministic</option>
              </select>
            </div>
            <div className="col-span-2 sm:col-span-1">
              <label className="block text-xs font-medium text-slate-500 mb-1">Status</label>
              <select value={formData.status}
                onChange={(e) => setFormData((p) => ({ ...p, status: e.target.value }))}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500">
                <option value="active">Active</option>
                <option value="inactive">Inactive</option>
              </select>
            </div>
            <div className="col-span-2">
              <label className="block text-xs font-medium text-slate-500 mb-1">Description</label>
              <input value={formData.description || ""}
                onChange={(e) => setFormData((p) => ({ ...p, description: e.target.value }))}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500" />
            </div>
            <div className="col-span-2">
              <label className="block text-xs font-medium text-slate-500 mb-1">Rules JSON</label>
              <textarea value={JSON.stringify(formData.rules_json, null, 2)}
                onChange={(e) => {
                  try {
                    const parsed = JSON.parse(e.target.value);
                    setFormData((p) => ({ ...p, rules_json: parsed }));
                  } catch { /* ignore invalid JSON */ }
                }}
                rows={6}
                className="w-full px-3 py-2 font-mono text-xs border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500" />
            </div>
          </div>
          <div className="flex gap-2 pt-2">
            <button onClick={handleSave}
              className="px-4 py-2 text-sm font-medium rounded-lg bg-blue-600 text-white hover:bg-blue-700 transition-colors">
              Save
            </button>
            <button onClick={cancelForm}
              className="px-4 py-2 text-sm font-medium rounded-lg border border-slate-300 text-slate-700 hover:bg-slate-100 transition-colors">
              Cancel
            </button>
          </div>
        </div>
      )}

      <DataTable
        columns={ruleColumns}
        data={filtered}
        loading={loading}
        error={error}
        onRetry={fetchRules}
        emptyMessage="No rules found."
      />

      <ConfirmDialog
        open={confirmAction !== null}
        title={confirmAction?.newStatus === "active" ? "Activate Rule" : "Deactivate Rule"}
        message={`Are you sure you want to ${confirmAction?.newStatus === "active" ? "activate" : "deactivate"} "${confirmAction?.name}"?`}
        confirmLabel={confirmAction?.newStatus === "active" ? "Activate" : "Deactivate"}
        variant="danger"
        onConfirm={handleToggleStatus}
        onCancel={() => setConfirmAction(null)}
      />
    </PageShell>
  )
}
