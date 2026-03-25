import { Route, Routes } from 'react-router-dom'

import { CompareRulesPage } from '@/pages/CompareRulesPage'
import compareRules from '@/test/fixtures/compare-rules.json'
import { mockRouteResponses } from '@/test/mock-fetch'
import { renderWithProviders } from '@/test/test-utils'

describe('CompareRulesPage', () => {
  it('reconstructs compare state from URL and renders side-by-side sections', async () => {
    mockRouteResponses({ '/browser/compare/rules': { body: compareRules } })
    const ids = compareRules.rules.map((rule) => rule.doc_id).join(',')
    const { findByText, getByTestId } = renderWithProviders(
      <Routes>
        <Route path="/compare/rules" element={<CompareRulesPage />} />
      </Routes>,
      { routerProps: { initialEntries: [`/compare/rules?ids=${encodeURIComponent(ids)}`] } },
    )

    await findByText('Rule Compare')

    expect(getByTestId('rule-compare-summary')).toBeInTheDocument()
    expect(getByTestId('rule-compare-table')).toBeInTheDocument()
    expect(await findByText(compareRules.rules[0]!.title)).toBeInTheDocument()
    expect(await findByText(compareRules.rules[1]!.title)).toBeInTheDocument()
  })
})
