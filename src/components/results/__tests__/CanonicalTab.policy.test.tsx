import { render, screen } from '@testing-library/react'
import { CanonicalTab } from '../CanonicalTab'
import type { CanonicalBundle } from '../../../types/extraction'

describe('CanonicalTab (policy conversion)', () => {
  it('renders policy conversion fields', () => {
    const canonical: CanonicalBundle = {
      generatedAt: '2025-12-10T10:00:00Z',
      policyConversion: {
        'Benefit Type': { value: 'Comprehensive', confidence: 0.92, sources: [{ page: 1 }] },
        'Maximum Lifetime $Benefit': { value: '$250,000', confidence: 0.8, sources: [{ page: 2 }] },
      },
    }

    render(<CanonicalTab canonical={canonical} isLoading={false} />)

    expect(screen.getByText('Benefit Type')).toBeInTheDocument()
    expect(screen.getByText('Comprehensive')).toBeInTheDocument()
    expect(screen.getByText('Maximum Lifetime $Benefit')).toBeInTheDocument()
    expect(screen.getByText('$250,000')).toBeInTheDocument()
  })

  it('shows empty state when canonical is missing', () => {
    render(<CanonicalTab canonical={null} isLoading={false} />)
    expect(screen.getByText(/No canonical mapping generated yet/i)).toBeInTheDocument()
  })
})
