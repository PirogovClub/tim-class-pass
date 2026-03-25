import { SupportBadges } from '@/components/detail/SupportBadges'
import { renderWithProviders } from '@/test/test-utils'

describe('SupportBadges', () => {
  it('renders badges for supplied metadata', () => {
    const { getByText } = renderWithProviders(<SupportBadges supportBasis="transcript_plus_visual" evidenceRequirement="required" teachingMode="example" confidenceScore={0.8} />)
    expect(getByText(/Transcript/)).toBeInTheDocument()
    expect(getByText(/Evidence: required/)).toBeInTheDocument()
    expect(getByText(/Mode: example/)).toBeInTheDocument()
    expect(getByText('80%')).toBeInTheDocument()
  })
})
