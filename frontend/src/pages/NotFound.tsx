import { Link } from 'react-router-dom'

export default function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center py-24 text-center">
      <p className="text-6xl font-bold text-slate-200">404</p>
      <h2 className="mt-4 text-xl font-semibold text-slate-800">
        Page not found
      </h2>
      <p className="mt-2 text-sm text-slate-500">
        The page you're looking for doesn't exist.
      </p>
      <Link
        to="/dashboard"
        className="mt-6 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700"
      >
        Go to Dashboard
      </Link>
    </div>
  )
}
