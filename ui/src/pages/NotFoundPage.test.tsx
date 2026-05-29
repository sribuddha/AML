import { describe, it, expect } from "vitest"
import { render, screen } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import NotFoundPage from "./NotFoundPage"

function renderPage() {
  return render(
    <MemoryRouter>
      <NotFoundPage />
    </MemoryRouter>
  )
}

describe("NotFoundPage", () => {
  it("renders 404 heading", () => {
    renderPage()
    expect(screen.getByText("404")).toBeInTheDocument()
  })

  it("renders Page not found title", () => {
    renderPage()
    expect(screen.getByText("Page not found")).toBeInTheDocument()
  })

  it("renders descriptive text", () => {
    renderPage()
    expect(screen.getByText(/does not exist or has been moved/i)).toBeInTheDocument()
  })

  it("renders Go home link pointing to /", () => {
    renderPage()
    const link = screen.getByText("Go home")
    expect(link).toBeInTheDocument()
    expect(link).toHaveAttribute("href", "/")
  })
})
