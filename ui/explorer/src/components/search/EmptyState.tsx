import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

type EmptyStateProps = { title?: string; description?: string; onClearFilters?: () => void }
export function EmptyState({ title = 'No results found', description = 'Try adjusting your filters or broadening your search query.', onClearFilters }: EmptyStateProps) {
  return <Card><CardHeader><CardTitle>{title}</CardTitle></CardHeader><CardContent className="space-y-3 text-sm text-slate-600"><p>{description}</p>{onClearFilters ? <Button type="button" variant="outline" size="sm" onClick={onClearFilters}>Clear filters</Button> : null}</CardContent></Card>
}
