import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import WorkspacePage from '../WorkspacePage'
import { useViewerStore } from '../../state/viewerStore'

const jsonResponse = (payload: unknown, status = 200) =>
  new Response(JSON.stringify(payload), {
    status,
    headers: {
      'Content-Type': 'application/json'
    }
  })

describe('WorkspacePage canonical integration', () => {
  afterEach(() => {
    vi.restoreAllMocks()
    const store = useViewerStore.getState()
    store.setJobId(null)
    store.setCurrentPage(1)
    store.setTotalPages(0)
    store.setSelectedTab('fields')
    if (store.showBoundingBoxes) {
      store.toggleBoundingBoxes()
    }
  })

  it('renders canonical bundle data when the API provides a response', async () => {
    const jobId = 'job-123'

    const jobStatusPayload = {
      jobId,
      totalPages: 1,
      processedPages: 1,
      state: 'completed',
      errors: [],
      startedAt: '2024-01-01T00:00:00Z',
      finishedAt: '2024-01-01T00:01:00Z',
      documentType: 'INVOICE',
      documentTypes: ['INVOICE']
    }

    const pagePayload = {
      pageNumber: 1,
      status: 'completed',
      fields: [
        {
          id: 'field-1',
          page: 1,
          name: 'Policy number',
          value: 'POL-123',
          confidence: 0.96
        }
      ],
      tables: [],
      imageUrl: undefined,
      errorMessage: null,
      rotationApplied: 0,
      documentTypeHint: 'INVOICE',
      documentTypeConfidence: 0.9
    }

    const canonicalPayload = {
      jobId,
      canonical: {
        documentCategories: ['INVOICE'],
        documentTypes: ['INVOICE'],
        invoice: {
          'Policy number': {
            value: 'POL-123',
            confidence: 0.98,
            sources: [{ page: 1, fieldId: 'field-1' }]
          }
        }
      },
      trace: { model: 'stub' },
      documentCategories: ['INVOICE'],
      documentTypes: ['INVOICE'],
      pageCategories: { 1: 'invoice' },
      pageClassifications: [{ page: 1, label: 'invoice', confidence: 0.9 }]
    }

    const responses = new Map<string, () => Response>([
      ['/api/jobs/job-123/status', () => jsonResponse(jobStatusPayload)],
      ['/api/jobs/job-123/pages/1', () => jsonResponse(pagePayload)],
      ['/api/jobs/job-123/canonical', () => jsonResponse(canonicalPayload)]
    ])

    const fetchMock = vi
      .spyOn(globalThis, 'fetch')
      .mockImplementation((input: RequestInfo | URL) => {
        const url = typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url
        const { pathname } = new URL(url, 'http://localhost')
        const handler = responses.get(pathname)
        if (!handler) {
          return Promise.resolve(jsonResponse({ detail: 'Not found' }, 404))
        }
        return Promise.resolve(handler())
      })

    const queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false
        }
      }
    })

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={[`/workspace/${jobId}`]}>
          <Routes>
            <Route path="/workspace/:jobId" element={<WorkspacePage />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    )

    const canonicalTab = await screen.findByRole('button', { name: /canonical/i })
    await waitFor(() => expect(canonicalTab).not.toBeDisabled())

    await userEvent.click(canonicalTab)

    expect(await screen.findByText('POL-123')).toBeInTheDocument()

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/jobs/job-123/canonical'),
      expect.objectContaining({ headers: expect.any(Object) })
    )
  })
})
