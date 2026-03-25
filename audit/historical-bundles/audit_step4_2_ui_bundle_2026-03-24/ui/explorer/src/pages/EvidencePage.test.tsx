import evidenceDetail from '@/test/fixtures/evidence-detail.json'
import { Route, Routes } from 'react-router-dom'

import { EvidencePage } from '@/pages/EvidencePage'
import { mockRouteResponses } from '@/test/mock-fetch'
import { renderWithProviders, waitFor } from '@/test/test-utils'

describe('EvidencePage', () => {
  it('renders evidence detail payload with screenshot affordance', async () => {
    mockRouteResponses({ [`/browser/evidence/${encodeURIComponent(evidenceDetail.doc_id)}`]: { body: evidenceDetail } })
    const { getAllByText, getByRole, getByTestId, getByText } = renderWithProviders(
      <Routes>
        <Route path="/evidence/:docId" element={<EvidencePage />} />
      </Routes>,
      { routerProps: { initialEntries: [`/evidence/${encodeURIComponent(evidenceDetail.doc_id)}`] } },
    )

    await waitFor(() => expect(getByRole('heading', { name: evidenceDetail.title })).toBeInTheDocument())

    expect(getByRole('link', { name: /back to search/i })).toBeInTheDocument()
    expect(getByRole('button', { name: /copy link/i })).toBeInTheDocument()
    expect(getAllByText('Transcript + Visual').length).toBeGreaterThan(0)
    expect(getByText('Strength:')).toBeInTheDocument()
    expect(getByText('Role:')).toBeInTheDocument()
    expect(getByTestId('evidence-snippet')).toHaveTextContent(evidenceDetail.snippet)
    expect(getByText('Timestamps')).toBeInTheDocument()
    expect(getByTestId('source-rules')).toBeInTheDocument()
    expect(getByRole('button', { name: /view 2 screenshots/i })).toBeInTheDocument()
  })
})
