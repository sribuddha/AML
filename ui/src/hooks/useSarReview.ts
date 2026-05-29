import { useState, useEffect, useCallback, useMemo } from "react"
import { api, ApiError } from "../api/client"
import { toast } from "../lib/toast"
import type { PendingSAR, PaginatedResponse } from "../types"

interface UseSarReviewOptions {
  uploadId?: string | null
  customerId?: string | null
}

export interface UseSarReviewReturn {
  sars: PendingSAR[]
  filteredSars: PendingSAR[]
  loading: boolean
  error: string | null
  completed: boolean
  reviewing: string | null
  batchReviewing: boolean
  selectedIds: Set<string>
  riskLevel: string
  customerName: string
  setRiskLevel: (level: string) => void
  toggleSelect: (sarId: string) => void
  toggleSelectAll: () => void
  review: (sarId: string, action: "confirmed" | "dismissed") => Promise<void>
  batchReview: (action: "confirmed" | "dismissed") => Promise<void>
  refetch: () => Promise<void>
}

export function useSarReview({ uploadId, customerId }: UseSarReviewOptions = {}): UseSarReviewReturn {
  const [sars, setSars] = useState<PendingSAR[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [reviewing, setReviewing] = useState<string | null>(null)
  const [batchReviewing, setBatchReviewing] = useState(false)
  const [completed, setCompleted] = useState(false)
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [riskLevel, setRiskLevel] = useState("all")
  const [customerName, setCustomerName] = useState("")

  const fetchSars = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await api.get<PaginatedResponse<PendingSAR>>("/api/sar/pending", {
        upload_id: uploadId || undefined,
        customer_id: customerId || undefined,
        per_page: 100,
      })
      setSars(result.items)
      setCompleted(result.items.length === 0)
      if (result.items.length > 0 && result.items[0].customer_first_name) {
        setCustomerName(`${result.items[0].customer_first_name} ${result.items[0].customer_last_name}`)
      } else {
        setCustomerName("")
      }
    } catch (e: unknown) {
      if (e instanceof ApiError && e.status === 404) {
        setCompleted(true)
      } else {
        setError(e instanceof Error ? e.message : "Failed to load")
      }
    } finally {
      setLoading(false)
    }
  }, [uploadId, customerId])

  useEffect(() => { fetchSars() }, [fetchSars])

  const filteredSars = useMemo(
    () => riskLevel === "all" ? sars : sars.filter((s) => s.risk_level === riskLevel),
    [sars, riskLevel],
  )

  const toggleSelect = useCallback((sarId: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(sarId)) next.delete(sarId)
      else next.add(sarId)
      return next
    })
  }, [])

  const toggleSelectAll = useCallback(() => {
    setSelectedIds((prev) =>
      prev.size === filteredSars.length
        ? new Set()
        : new Set(filteredSars.map((s) => s.sar_id)),
    )
  }, [filteredSars])

  const review = useCallback(async (sarId: string, action: "confirmed" | "dismissed") => {
    setReviewing(sarId)
    try {
      await api.patch(`/api/sar/${sarId}/review`, { action, notes: "" })
      await new Promise((r) => setTimeout(r, 1000))
      toast.success(`SAR ${action === "confirmed" ? "confirmed" : "dismissed"}`)
      setReviewing(null)
      await fetchSars()
      setSelectedIds(new Set())
      window.dispatchEvent(new CustomEvent("sar-reviewed"))
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Review failed")
      setReviewing(null)
    }
  }, [fetchSars])

  const batchReview = useCallback(async (action: "confirmed" | "dismissed") => {
    if (selectedIds.size === 0) return
    setBatchReviewing(true)
    try {
      await api.post("/api/sar/batch-review", { sar_ids: Array.from(selectedIds), action })
      await new Promise((r) => setTimeout(r, 1000))
      toast.success(`${selectedIds.size} SARs ${action === "confirmed" ? "confirmed" : "dismissed"}`)
      await fetchSars()
      setSelectedIds(new Set())
      window.dispatchEvent(new CustomEvent("sar-reviewed"))
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Batch review failed")
    } finally {
      setBatchReviewing(false)
    }
  }, [selectedIds, fetchSars])

  return {
    sars,
    filteredSars,
    loading,
    error,
    completed,
    reviewing,
    batchReviewing,
    selectedIds,
    riskLevel,
    customerName,
    setRiskLevel,
    toggleSelect,
    toggleSelectAll,
    review,
    batchReview,
    refetch: fetchSars,
  }
}
