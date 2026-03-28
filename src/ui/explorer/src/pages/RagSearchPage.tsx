import { Navigate } from 'react-router-dom'

/** Stage 6.4: hybrid analyst search lives on `/search`; `/rag` kept as a stable alias. */
export function RagSearchPage() {
  return <Navigate to="/search" replace />
}
