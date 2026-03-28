import { formatConfidence, formatTimestampRange } from '@/lib/utils/format'

describe('format utils', () => {
  it('formats confidence values', () => {
    expect(formatConfidence(0.9)).toBe('90%')
    expect(formatConfidence(null)).toBeNull()
  })

  it('formats timestamp ranges', () => {
    expect(formatTimestampRange({ start: '00:36', end: '00:40' })).toBe('00:36–00:40')
    expect(formatTimestampRange({ start: '01:03', end: '01:03' })).toBe('01:03')
  })
})
