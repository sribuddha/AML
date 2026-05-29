import { describe, it, expect, vi, afterEach } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import ErrorBoundary from "./ErrorBoundary"

let consoleError = console.error

function Bomb({ shouldThrow = true }: { shouldThrow?: boolean }) {
  if (shouldThrow) throw new Error("💥")
  return <div>All good</div>
}

describe("ErrorBoundary", () => {
  afterEach(() => {
    console.error = consoleError
  })

  it("renders children when no error", () => {
    render(
      <ErrorBoundary>
        <div>Safe</div>
      </ErrorBoundary>
    )
    expect(screen.getByText("Safe")).toBeInTheDocument()
  })

  it("renders default fallback on error", () => {
    console.error = vi.fn()
    render(
      <ErrorBoundary>
        <Bomb />
      </ErrorBoundary>
    )
    expect(screen.getByText("Something went wrong")).toBeInTheDocument()
    expect(screen.getByText("💥")).toBeInTheDocument()
    expect(screen.getByText("Try again")).toBeInTheDocument()
  })

  it("renders custom fallback element", () => {
    console.error = vi.fn()
    render(
      <ErrorBoundary fallback={<div>Custom error page</div>}>
        <Bomb />
      </ErrorBoundary>
    )
    expect(screen.getByText("Custom error page")).toBeInTheDocument()
  })

  it("renders custom fallback function with error and reset", () => {
    console.error = vi.fn()
    const fallback = vi.fn((error: Error, reset: () => void) => (
      <div>
        <span>Err: {error.message}</span>
        <button onClick={reset}>Retry</button>
      </div>
    ))
    render(
      <ErrorBoundary fallback={fallback}>
        <Bomb />
      </ErrorBoundary>
    )
    expect(screen.getByText("Err: 💥")).toBeInTheDocument()
    expect(fallback.mock.calls[0][0].message).toBe("💥")
    const resetFn = fallback.mock.calls[0][1]
    expect(typeof resetFn).toBe("function")
  })

  it("calls onError when error occurs", () => {
    console.error = vi.fn()
    const onError = vi.fn()
    render(
      <ErrorBoundary onError={onError}>
        <Bomb />
      </ErrorBoundary>
    )
    expect(onError).toHaveBeenCalledTimes(1)
    expect(onError.mock.calls[0][0].message).toBe("💥")
  })

  it("reset via fallback re-renders children which may re-throw", () => {
    console.error = vi.fn()
    const fallback = (_error: Error, reset: () => void) => (
      <div>
        <span>Error state</span>
        <button onClick={reset}>Reset</button>
      </div>
    )
    render(
      <ErrorBoundary fallback={fallback}>
        <Bomb />
      </ErrorBoundary>
    )
    expect(screen.getByText("Error state")).toBeInTheDocument()
    fireEvent.click(screen.getByText("Reset"))
    // After reset, Bomb re-throws, so error state re-appears
    expect(screen.getByText("Error state")).toBeInTheDocument()
  })
})
