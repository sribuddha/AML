import { Link } from "react-router-dom"

export default function NotFoundPage() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] text-center">
      <div className="text-6xl font-bold text-slate-200 mb-4">404</div>
      <h2 className="text-xl font-semibold text-slate-800 mb-2">Page not found</h2>
      <p className="text-sm text-slate-500 mb-6">
        The page you are looking for does not exist or has been moved.
      </p>
      <Link
        to="/"
        className="px-4 py-2 text-sm font-medium rounded-lg bg-blue-600 text-white hover:bg-blue-700 transition-colors"
      >
        Go home
      </Link>
    </div>
  )
}
