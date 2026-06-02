import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { api, setApiKey, clearApiKey, getApiKey } from "../api/client"

export default function SettingsPage() {
  const navigate = useNavigate()
  const [key, setKey] = useState(getApiKey() || "")
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [testResult, setTestResult] = useState<string | null>(null)
  const hasStored = !!getApiKey()

  const handleSave = async () => {
    setSaving(true)
    setError(null)
    setTestResult(null)

    if (!key.trim()) {
      clearApiKey()
      navigate("/")
      return
    }

    try {
      await api.get("/api/uploads", { limit: "1" })
      setApiKey(key)
      setTestResult("API key is valid")
      setTimeout(() => navigate("/"), 1000)
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Failed to validate key"
      setError(msg)
    } finally {
      setSaving(false)
    }
  }

  const handleClear = () => {
    clearApiKey()
    setKey("")
    setError(null)
    setTestResult(null)
    navigate("/")
  }

  return (
    <div className="max-w-md mx-auto mt-12">
      <h2 className="text-xl font-bold text-slate-800 mb-2">Settings</h2>
      <p className="text-sm text-slate-500 mb-6">
        Enter the shared API key to access the application. The key is stored in your browser and never sent to the server outside of API requests.
      </p>

      <div className="bg-white border border-slate-200 rounded-lg p-6 space-y-4">
        <div>
          <label htmlFor="api-key" className="block text-sm font-medium text-slate-700 mb-1">API Key</label>
          <input
            id="api-key"
            type="password"
            value={key}
            onChange={(e) => { setKey(e.target.value); setError(null); setTestResult(null) }}
            placeholder="Enter API key or leave blank for dev mode"
            className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            autoFocus
          />
        </div>

        {error && (
          <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
            {error}
          </div>
        )}

        {testResult && (
          <div className="text-sm text-green-600 bg-green-50 border border-green-200 rounded-lg px-3 py-2">
            {testResult}
          </div>
        )}

        <div className="flex gap-3">
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex-1 px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            {saving ? "Testing..." : "Save"}
          </button>
          {hasStored && (
            <button
              onClick={handleClear}
              className="px-4 py-2 bg-white text-red-600 text-sm font-medium rounded-lg border border-red-300 hover:bg-red-50 transition-colors"
            >
              Clear
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
