import { Link } from 'react-router-dom'

export function TopBar() {
  const title = import.meta.env.VITE_APP_TITLE ?? 'Trading Explorer'

  return (
    <header className="border-b border-slate-200 bg-white/90 backdrop-blur">
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-3 sm:px-6 lg:px-8">
        <div>
          <Link to="/search" className="text-lg font-semibold text-slate-900">
            {title}
          </Link>
          <p className="text-sm text-slate-500">Thin, read-only analyst browser for Step 4 explorer data.</p>
          <nav className="mt-2 flex flex-wrap gap-3 text-sm">
            <Link to="/search" className="text-blue-700 hover:underline">
              Search
            </Link>
            <Link to="/review/queue" className="text-blue-700 hover:underline">
              Review queue
            </Link>
          </nav>
        </div>
      </div>
    </header>
  )
}
