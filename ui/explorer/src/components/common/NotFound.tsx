import { Link } from 'react-router-dom'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

type NotFoundProps = { title?: string; description?: string; message?: string }
export function NotFound({ title = 'Not Found', description, message }: NotFoundProps) {
  const text = description ?? message ?? 'Entity not found. It may have been removed or the ID is incorrect.'
  return <div className="mx-auto max-w-3xl p-6"><Card><CardHeader><CardTitle>{title}</CardTitle></CardHeader><CardContent className="space-y-4 text-sm text-slate-600"><p>{text}</p><Link className="font-medium text-teal-700 underline-offset-4 hover:underline" to="/search">Back to search</Link></CardContent></Card></div>
}
