import type { AggregatedResults, ExtractionJob, PageExtraction } from '../types/extraction'

const mockPages: PageExtraction[] = [
  {
    pageNumber: 1,
    status: 'completed',
    imageUrl: '/mock/invoice-page-1.png',
    fields: [
      {
        id: 'field-invoice-number',
        page: 1,
        name: 'Invoice Number',
        value: 'INV-2048',
        confidence: 0.98,
        bbox: { x: 0.62, y: 0.12, width: 0.25, height: 0.05 }
      },
      {
        id: 'field-invoice-date',
        page: 1,
        name: 'Invoice Date',
        value: '2025-08-17',
        confidence: 0.94,
        bbox: { x: 0.62, y: 0.19, width: 0.22, height: 0.05 }
      },
      {
        id: 'field-total-due',
        page: 1,
        name: 'Total Due',
        value: '$4,280.00',
        confidence: 0.91,
        bbox: { x: 0.62, y: 0.26, width: 0.2, height: 0.05 }
      }
    ],
    tables: [
      {
        id: 'table-line-items',
        page: 1,
        caption: 'Line Items',
        confidence: 0.9,
        columns: [
          { key: 'item', header: 'Item', type: 'string', confidence: 0.9 },
          { key: 'qty', header: 'Qty', type: 'number', confidence: 0.84 },
          { key: 'unitCost', header: 'Unit Cost', type: 'number', confidence: 0.82 },
          { key: 'lineTotal', header: 'Line Total', type: 'number', confidence: 0.87 }
        ],
        rows: [
          [
            { value: 'Enterprise License', confidence: 0.93 },
            { value: '10', confidence: 0.88 },
            { value: '$320.00', confidence: 0.82 },
            { value: '$3,200.00', confidence: 0.86 }
          ],
          [
            { value: 'Implementation Support', confidence: 0.9 },
            { value: '20', confidence: 0.83 },
            { value: '$40.00', confidence: 0.8 },
            { value: '$800.00', confidence: 0.85 }
          ],
          [
            { value: 'Premium SLA', confidence: 0.91 },
            { value: '1', confidence: 0.9 },
            { value: '$280.00', confidence: 0.82 },
            { value: '$280.00', confidence: 0.86 }
          ]
        ],
        bbox: { x: 0.07, y: 0.45, width: 0.86, height: 0.34 }
      }
    ]
  },
  {
    pageNumber: 2,
    status: 'completed',
    imageUrl: '/mock/invoice-page-2.png',
    fields: [
      {
        id: 'field-bill-to',
        page: 2,
        name: 'Bill To',
        value: 'Northwind Analytics\n400 Sunset Ave\nSeattle, WA 98101',
        confidence: 0.88,
        bbox: { x: 0.08, y: 0.14, width: 0.38, height: 0.22 }
      },
      {
        id: 'field-ship-to',
        page: 2,
        name: 'Ship To',
        value: 'Northwind Analytics\n410 Harbor Blvd\nSeattle, WA 98102',
        confidence: 0.87,
        bbox: { x: 0.53, y: 0.14, width: 0.38, height: 0.22 }
      },
      {
        id: 'field-payment-terms',
        page: 2,
        name: 'Payment Terms',
        value: 'Net 30',
        confidence: 0.81,
        bbox: { x: 0.08, y: 0.41, width: 0.24, height: 0.05 }
      }
    ],
    tables: []
  },
  {
    pageNumber: 3,
    status: 'completed',
    imageUrl: '/mock/invoice-page-3.png',
    fields: [
      {
        id: 'field-notes',
        page: 3,
        name: 'Notes',
        value: 'Please remit payment via ACH. Late fees apply after 45 days.',
        confidence: 0.76,
        bbox: { x: 0.09, y: 0.2, width: 0.82, height: 0.12 }
      }
    ],
    tables: [
      {
        id: 'table-payment-history',
        page: 3,
        caption: 'Payment History',
        confidence: 0.78,
        columns: [
          { key: 'date', header: 'Date', type: 'date', confidence: 0.76 },
          { key: 'method', header: 'Method', type: 'string', confidence: 0.75 },
          { key: 'amount', header: 'Amount', type: 'number', confidence: 0.74 }
        ],
        rows: [
          [
            { value: '2025-05-12', confidence: 0.76 },
            { value: 'ACH', confidence: 0.7 },
            { value: '$2,100.00', confidence: 0.73 }
          ],
          [
            { value: '2025-04-10', confidence: 0.75 },
            { value: 'Check', confidence: 0.71 },
            { value: '$2,180.00', confidence: 0.72 }
          ]
        ],
        bbox: { x: 0.08, y: 0.48, width: 0.84, height: 0.26 }
      }
    ]
  }
]

const aggregated: AggregatedResults = {
  jobId: 'demo-job',
  fields: [
    {
      canonicalName: 'Invoice Number',
      pages: [1],
      values: [{ page: 1, value: 'INV-2048', confidence: 0.98 }],
      bestValue: 'INV-2048',
      confidenceStats: { min: 0.98, max: 0.98, avg: 0.98 }
    },
    {
      canonicalName: 'Invoice Date',
      pages: [1],
      values: [{ page: 1, value: '2025-08-17', confidence: 0.94 }],
      bestValue: '2025-08-17',
      confidenceStats: { min: 0.94, max: 0.94, avg: 0.94 }
    },
    {
      canonicalName: 'Total Due',
      pages: [1],
      values: [{ page: 1, value: '$4,280.00', confidence: 0.91 }],
      bestValue: '$4,280.00',
      confidenceStats: { min: 0.91, max: 0.91, avg: 0.91 }
    },
    {
      canonicalName: 'Payment Terms',
      pages: [2],
      values: [{ page: 2, value: 'Net 30', confidence: 0.81 }],
      bestValue: 'Net 30',
      confidenceStats: { min: 0.81, max: 0.81, avg: 0.81 }
    }
  ]
}

export const mockExtractionJob: ExtractionJob = {
  status: {
    jobId: 'demo-job',
    totalPages: mockPages.length,
    processedPages: mockPages.length,
    state: 'completed',
    startedAt: '2025-08-17T18:35:00.000Z',
    finishedAt: '2025-08-17T18:35:12.000Z'
  },
  pages: mockPages,
  aggregated
}
