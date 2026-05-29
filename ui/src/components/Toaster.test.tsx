import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent, act } from "@testing-library/react"
import Toaster from "./Toaster"

const { mockSubscribe, mockDismiss } = vi.hoisted(() => ({
  mockSubscribe: vi.fn(),
  mockDismiss: vi.fn(),
}))

vi.mock("../lib/toast", () => ({
  subscribe: mockSubscribe,
  dismiss: mockDismiss,
  toast: Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn() }),
}))

function triggerToasts(toasts: { id: string; message: string; variant: string; duration: number }[]) {
  const cb = mockSubscribe.mock.calls[0]?.[0]
  if (cb) act(() => cb([...toasts]))
}

describe("Toaster", () => {
  beforeEach(() => {
    mockSubscribe.mockReset()
    mockDismiss.mockReset()
  })

  it("renders nothing when no toasts", () => {
    mockSubscribe.mockImplementation(() => () => {})
    const { container } = render(<Toaster />)
    expect(container.innerHTML).toBe("")
  })

  it("renders toast message", () => {
    mockSubscribe.mockImplementation(() => () => {})
    render(<Toaster />)
    triggerToasts([{ id: "1", message: "Hello", variant: "info", duration: 4000 }])
    expect(screen.getByText("Hello")).toBeInTheDocument()
  })

  it("dismisses toast on × click", () => {
    mockSubscribe.mockImplementation(() => () => {})
    render(<Toaster />)
    triggerToasts([{ id: "1", message: "Dismiss me", variant: "info", duration: 4000 }])
    expect(screen.getByText("Dismiss me")).toBeInTheDocument()
    fireEvent.click(screen.getByText("×"))
    expect(mockDismiss).toHaveBeenCalledWith("1")
  })

  it("renders multiple toasts", () => {
    mockSubscribe.mockImplementation(() => () => {})
    render(<Toaster />)
    triggerToasts([
      { id: "1", message: "First", variant: "info", duration: 4000 },
      { id: "2", message: "Second", variant: "success", duration: 4000 },
    ])
    expect(screen.getByText("First")).toBeInTheDocument()
    expect(screen.getByText("Second")).toBeInTheDocument()
  })

  it("updates when toasts array changes", () => {
    mockSubscribe.mockImplementation(() => () => {})
    render(<Toaster />)
    triggerToasts([{ id: "1", message: "Temp", variant: "info", duration: 1000 }])
    expect(screen.getByText("Temp")).toBeInTheDocument()
    triggerToasts([])
    expect(screen.queryByText("Temp")).not.toBeInTheDocument()
  })

  it("applies success variant style", () => {
    mockSubscribe.mockImplementation(() => () => {})
    render(<Toaster />)
    triggerToasts([{ id: "1", message: "Green", variant: "success", duration: 4000 }])
    const el = screen.getByText("Green").parentElement!
    expect(el.className).toContain("bg-green-600")
  })

  it("applies error variant style", () => {
    mockSubscribe.mockImplementation(() => () => {})
    render(<Toaster />)
    triggerToasts([{ id: "1", message: "Red", variant: "error", duration: 4000 }])
    const el = screen.getByText("Red").parentElement!
    expect(el.className).toContain("bg-red-600")
  })

  it("applies warning variant style", () => {
    mockSubscribe.mockImplementation(() => () => {})
    render(<Toaster />)
    triggerToasts([{ id: "1", message: "Amber", variant: "warning", duration: 4000 }])
    const el = screen.getByText("Amber").parentElement!
    expect(el.className).toContain("bg-amber-500")
  })

  it("applies info variant style", () => {
    mockSubscribe.mockImplementation(() => () => {})
    render(<Toaster />)
    triggerToasts([{ id: "1", message: "Slate", variant: "info", duration: 4000 }])
    const el = screen.getByText("Slate").parentElement!
    expect(el.className).toContain("bg-slate-800")
  })
})
