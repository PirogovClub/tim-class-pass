import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { RagSearchPage } from '@/pages/RagSearchPage'

describe('RagSearchPage', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('submits query and renders hits', async () => {
    const user = userEvent.setup()
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({
          query: 'stop',
          top_hits: [
            {
              doc_id: 'rule:x:r1',
              unit_type: 'rule_card',
              lesson_id: 'lesson_alpha',
              text_snippet: 'Rule text',
              score: 0.9,
            },
          ],
          query_analysis: { normalized_query: 'stop' },
          summary: { answer_text: 'Summary line' },
        }),
      }),
    )

    render(
      <MemoryRouter>
        <RagSearchPage />
      </MemoryRouter>,
    )

    await user.type(screen.getByLabelText(/query/i), 'stop')
    await user.click(screen.getByRole('button', { name: /search/i }))

    await waitFor(() => {
      expect(screen.getByText(/Hits \(1\)/)).toBeInTheDocument()
    })
    expect(screen.getByText('Rule text')).toBeInTheDocument()
  })
})
