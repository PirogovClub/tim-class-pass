import { vi } from 'vitest'

import { FilterChips } from '@/components/filters/FilterChips'
import { renderWithProviders } from '@/test/test-utils'

describe('FilterChips', () => {
  it('renders chips and handles removal', () => {
    const onRemove = vi.fn()
    const { getByText } = renderWithProviders(<FilterChips chips={[{ key: 'lesson:a', label: 'Lesson A', onRemove }]} />)
    const button = getByText('Lesson A')
    expect(button).toBeInTheDocument()
    button.click()
    expect(onRemove).toHaveBeenCalled()
  })
})
