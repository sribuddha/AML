import { describe, it, expect, vi, beforeEach, afterEach } from "vitest"

async function freshToast() {
  vi.resetModules()
  return import("./toast")
}

describe("toast", () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it("notifies subscribers when dispatched", async () => {
    const { toast, subscribe } = await freshToast()
    const listener = vi.fn()
    const unsub = subscribe(listener)
    toast("hello")
    expect(listener).toHaveBeenCalledTimes(1)
    const toasts = listener.mock.calls[0][0]
    expect(toasts).toHaveLength(1)
    expect(toasts[0].message).toBe("hello")
    expect(toasts[0].variant).toBe("info")
    unsub()
  })

  it("removes toast after duration", async () => {
    const { toast, subscribe } = await freshToast()
    const listener = vi.fn()
    subscribe(listener)
    toast("timed")
    expect(listener.mock.calls[0][0]).toHaveLength(1)
    vi.advanceTimersByTime(4000)
    expect(listener).toHaveBeenCalledTimes(2)
    expect(listener.mock.calls[1][0]).toHaveLength(0)
  })

  it("dismiss removes toast immediately", async () => {
    const { toast, subscribe, dismiss } = await freshToast()
    const listener = vi.fn()
    subscribe(listener)
    toast("dismiss me")
    const toasts = listener.mock.calls[0][0]
    dismiss(toasts[0].id)
    expect(listener).toHaveBeenCalledTimes(2)
    expect(listener.mock.calls[1][0]).toHaveLength(0)
  })

  it("toast.success dispatches success variant", async () => {
    const { toast, subscribe } = await freshToast()
    const listener = vi.fn()
    subscribe(listener)
    toast.success("ok")
    expect(listener.mock.calls[0][0][0].variant).toBe("success")
  })

  it("toast.error dispatches error variant", async () => {
    const { toast, subscribe } = await freshToast()
    const listener = vi.fn()
    subscribe(listener)
    toast.error("fail")
    expect(listener.mock.calls[0][0][0].variant).toBe("error")
  })

  it("toast.info dispatches info variant", async () => {
    const { toast, subscribe } = await freshToast()
    const listener = vi.fn()
    subscribe(listener)
    toast.info("info")
    expect(listener.mock.calls[0][0][0].variant).toBe("info")
  })

  it("toast.warning dispatches warning variant", async () => {
    const { toast, subscribe } = await freshToast()
    const listener = vi.fn()
    subscribe(listener)
    toast.warning("warn")
    expect(listener.mock.calls[0][0][0].variant).toBe("warning")
  })

  it("toast with object arg", async () => {
    const { toast, subscribe } = await freshToast()
    const listener = vi.fn()
    subscribe(listener)
    toast({ message: "custom", variant: "error", duration: 2000 })
    const t = listener.mock.calls[0][0][0]
    expect(t.message).toBe("custom")
    expect(t.variant).toBe("error")
    expect(t.duration).toBe(2000)
  })

  it("toast with object arg uses defaults", async () => {
    const { toast, subscribe } = await freshToast()
    const listener = vi.fn()
    subscribe(listener)
    toast({ message: "defaults" })
    const t = listener.mock.calls[0][0][0]
    expect(t.variant).toBe("info")
    expect(t.duration).toBe(4000)
  })

  it("unsubscribe stops notifications", async () => {
    const { toast, subscribe } = await freshToast()
    const listener = vi.fn()
    const unsub = subscribe(listener)
    unsub()
    toast("silent")
    expect(listener).not.toHaveBeenCalled()
  })

  it("generates unique ids", async () => {
    const { toast, subscribe } = await freshToast()
    const listener = vi.fn()
    subscribe(listener)
    toast("one")
    toast("two")
    const toasts = listener.mock.calls[listener.mock.calls.length - 1][0]
    expect(toasts[0].id).not.toBe(toasts[1].id)
  })
})
