import { Route, Routes } from 'react-router-dom'

import { RelatedRulesPage } from '@/pages/RelatedRulesPage'
import relatedRules from '@/test/fixtures/related-rules.json'
import ruleDetail from '@/test/fixtures/rule-detail.json'
import { mockRouteResponses } from '@/test/mock-fetch'
import { renderWithProviders } from '@/test/test-utils'

describe('RelatedRulesPage', () => {
  it('renders grouped relation reasons', async () => {
    const sourceRule = { ...ruleDetail, doc_id: relatedRules.source_doc_id, title: 'Accumulation near levels' }
    mockRouteResponses({
      [`/browser/rule/${encodeURIComponent(relatedRules.source_doc_id)}`]: { body: sourceRule },
      [`/browser/rule/${encodeURIComponent(relatedRules.source_doc_id)}/related`]: { body: relatedRules },
    })
    const { findByText, getByTestId } = renderWithProviders(
      <Routes>
        <Route path="/rule/:docId/related" element={<RelatedRulesPage />} />
      </Routes>,
      { routerProps: { initialEntries: [`/rule/${encodeURIComponent(relatedRules.source_doc_id)}/related`] } },
    )

    await findByText('Related Rules')

    expect(getByTestId('related-group-same_lesson')).toBeInTheDocument()
    expect(await findByText(/Same lesson/i)).toBeInTheDocument()
  })
})
