import { vi } from 'vitest'
import { renderWithProviders } from '@/test/test-utils'
import { FilterChips } from '@/components/filters/FilterChips'

describe('FilterChips', () => {
  it('renders chips and handles removal', async () => {
    const onRemove = vi.fn()
    const { getByText } = renderWithProviders(<FilterChips chips={[{ key: 'lesson:a', label: 'Lesson A', onRemove }]} />)
    const button = getByText('Lesson A')
    expect(button).toBeInTheDocument()
    button.click()
    expect(onRemove).toHaveBeenCalled()
  })
})
