import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import CanonicalTab from '../CanonicalTab'
import type { CanonicalBundle } from '../../../types/extraction'

describe('CanonicalTab UB-04 line items', () => {
  it('renders UB-04 line items provided as JSON string payloads', () => {
    const canonical: CanonicalBundle = {
      documentCategories: ['UB04'],
      documentTypes: ['UB04'],
      schemaVersion: 'test-1.0.0',
      ub04: {
        providerName: {
          value: 'Pleasanton Nursing & Rehabilitation Center',
          confidence: 0.82,
          sources: [{ page: 1, fieldId: 'provider_name' }],
        },
        'Line items (Boxes 42–47)': {
          value: JSON.stringify({
            tableId: 'table-1',
            headers: [
              { key: 'revenueCode', label: 'Revenue Code' },
              { key: 'description', label: 'Description' },
              { key: 'totalCharge', label: 'Total Charge' },
            ],
            items: [
              {
                revenueCode: '0022',
                description: 'Room and Board',
                totalCharge: '$1,000',
              },
            ],
          }),
          confidence: 0.71,
          sources: [{ page: 1, tableId: 'table-1' }],
        },
      },
      ub04LineItems: null,
      invoice: null,
      invoiceLineItems: null,
      cmr: null,
      sourceMap: null,
      identityBlocks: null,
      reasoningNotes: [],
      notes: [],
    }

    render(
      <CanonicalTab
        canonical={canonical}
        documentType="UB04"
        documentTypes={['UB04']}
        documentCategories={['UB04']}
        isLoading={false}
      />
    )

    expect(screen.getByText('UB-04')).toBeInTheDocument()
    expect(screen.getByText('Line items')).toBeInTheDocument()
    expect(screen.getByText('Room and Board')).toBeInTheDocument()
    expect(screen.getByText('0022')).toBeInTheDocument()
    expect(screen.getByText('$1,000')).toBeInTheDocument()
  })
})
