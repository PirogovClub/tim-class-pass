import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import { RagSearchPage } from '@/pages/RagSearchPage'

describe('RagSearchPage', () => {
  it('redirects to /search (Stage 6.4 unified analyst browser)', () => {
    render(
      <MemoryRouter initialEntries={['/rag']}>
        <Routes>
          <Route path="/rag" element={<RagSearchPage />} />
          <Route path="/search" element={<div>Unified search</div>} />
        </Routes>
      </MemoryRouter>,
    )
    expect(screen.getByText('Unified search')).toBeInTheDocument()
  })
})
