import { Route, Routes } from 'react-router-dom'

import { RulePage } from '@/pages/RulePage'
import ruleDetail from '@/test/fixtures/rule-detail.json'
import { mockRouteResponses } from '@/test/mock-fetch'
import { renderWithProviders } from '@/test/test-utils'

describe('RulePage', () => {
  it('renders rule detail payload', async () => {
    mockRouteResponses({ [`/browser/rule/${encodeURIComponent(ruleDetail.doc_id)}`]: { body: ruleDetail } })
    const { getAllByText, getByRole, getByTestId, getByText, findByRole } = renderWithProviders(
      <Routes>
        <Route path="/rule/:docId" element={<RulePage />} />
      </Routes>,
      { routerProps: { initialEntries: [`/rule/${encodeURIComponent(ruleDetail.doc_id)}`] } },
    )

    await findByRole('heading', { name: ruleDetail.title })

    expect(getByRole('link', { name: /back to search/i })).toBeInTheDocument()
    expect(getByRole('button', { name: /copy link/i })).toBeInTheDocument()
    expect(getAllByText('Transcript + Visual').length).toBeGreaterThan(0)
    expect(getByTestId('rule-text-ru')).toHaveTextContent(ruleDetail.rule_text_ru)
    expect(getByText('Timestamps')).toBeInTheDocument()
    expect(getByTestId('linked-evidence')).toBeInTheDocument()
    expect(getAllByText(/Related Rules/i).length).toBeGreaterThan(0)
    expect(getByRole('button', { name: /view 4 screenshots/i })).toBeInTheDocument()
  })
})
