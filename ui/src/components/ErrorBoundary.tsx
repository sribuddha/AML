import { Component, type ReactNode, type ErrorInfo } from "react"

interface ErrorBoundaryProps {
  children: ReactNode
  fallback?: ReactNode | ((error: Error, reset: () => void) => ReactNode)
  onError?: (error: Error, errorInfo: ErrorInfo) => void
}

interface ErrorBoundaryState {
  error: Error | null
}

export default class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { error: null }

  static getDerivedStateFromError(error: Error) {
    return { error }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    this.props.onError?.(error, errorInfo)
  }

  handleReset = () => {
    this.setState({ error: null })
  }

  render() {
    if (!this.state.error) return this.props.children

    const { fallback } = this.props
    if (fallback !== undefined) {
      if (typeof fallback === "function") {
        return (fallback as (error: Error, reset: () => void) => ReactNode)(this.state.error, this.handleReset)
      }
      return fallback
    }

    return (
      <div className="flex flex-col items-center justify-center min-h-[200px] p-8 text-center">
        <div className="text-3xl mb-3">&#9888;</div>
        <h2 className="text-lg font-semibold text-slate-800 mb-1">Something went wrong</h2>
        <p className="text-sm text-slate-500 mb-4 max-w-md">{this.state.error.message}</p>
        <button
          onClick={this.handleReset}
          className="px-4 py-2 text-sm font-medium rounded-lg bg-blue-600 text-white hover:bg-blue-700 transition-colors"
        >
          Try again
        </button>
      </div>
    )
  }
}
