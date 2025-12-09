import type {
  AggregatedResults,
  CanonicalBundle,
  CanonicalBundleResponse,
  CanonicalGroupRecord,
  DashboardMetrics,
  JobHistoryDetail,
  JobHistorySummary,
  JobStatus,
  LowConfidenceField,
  PageExtraction,
  SaveEditsRequest,
  SaveEditsResponse,
  UploadResponse
} from '../types/extraction'
import { collectCanonicalFields } from '../utils/canonical'

const DEFAULT_API_BASE_URL = 'http://127.0.0.1:8000'
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? DEFAULT_API_BASE_URL

const jsonHeaders = {
  Accept: 'application/json',
  'Content-Type': 'application/json'
}

const buildUrl = (path: string) => {
  if (path.startsWith('http')) {
    return path
  }
  const trimmedBase = API_BASE_URL.replace(/\/$/, '')
  const normalizedPath = path.startsWith('/') ? path : `/${path}`
  return `${trimmedBase}${normalizedPath}`
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let detail = response.statusText
    try {
      const data = await response.json()
      detail = (data as { detail?: string }).detail ?? detail
    } catch (error) {
      void error
    }
    throw new Error(detail || `Request failed with status ${response.status}`)
  }
  return (await response.json()) as T
}

const toAbsoluteUrl = (url?: string | null): string | undefined => {
  if (!url) return undefined
  if (/^https?:\/\//i.test(url)) {
    return url
  }
  if (url.startsWith('//')) {
    try {
      const apiUrl = new URL(API_BASE_URL)
      return `${apiUrl.protocol}${url}`
    } catch (error) {
      void error
    }
  }
  return buildUrl(url)
}

const normalizePage = (page: PageExtraction): PageExtraction => ({
  ...page,
  imageUrl: toAbsoluteUrl(page.imageUrl)
})

const isRecord = (value: unknown): value is Record<string, unknown> =>
  Boolean(value && typeof value === 'object' && !Array.isArray(value))

const normalizeCanonicalBundle = (bundle?: CanonicalBundle | null): CanonicalBundle | null => {
  if (!bundle) {
    return null
  }
  const reasoningNotes = Array.isArray(bundle.reasoningNotes)
    ? bundle.reasoningNotes
    : Array.isArray(bundle.notes)
      ? bundle.notes
      : []
  const facilityInvoiceSection = (bundle as Record<string, unknown>).facilityInvoice
  const facilityInvoiceGeneral = isRecord(facilityInvoiceSection) && isRecord((facilityInvoiceSection as Record<string, unknown>).general)
    ? collectCanonicalFields((facilityInvoiceSection as { general: Record<string, unknown> }).general)
    : undefined
  const facilityInvoiceLineItems = isRecord(facilityInvoiceSection) && Array.isArray((facilityInvoiceSection as Record<string, unknown>).lineItems)
    ? ((facilityInvoiceSection as { lineItems: Array<Record<string, unknown>> }).lineItems)
    : undefined

  const ub04LineItemsSection = (bundle as Record<string, unknown>).ub04LineItems
  const normalizedUb04LineItems = Array.isArray(ub04LineItemsSection)
    ? (ub04LineItemsSection as CanonicalBundle['ub04LineItems'])
    : isRecord(ub04LineItemsSection)
      ? [ub04LineItemsSection as NonNullable<CanonicalBundle['ub04LineItems']>[number]]
      : undefined

  const cmrFormSection = (bundle as Record<string, unknown>).cmrForm
  const cmrGeneral = isRecord(cmrFormSection) && isRecord((cmrFormSection as Record<string, unknown>).general)
    ? collectCanonicalFields((cmrFormSection as { general: Record<string, unknown> }).general)
    : undefined

  const normalizedInvoice: CanonicalGroupRecord | undefined = facilityInvoiceGeneral
    ?? (bundle.invoice && isRecord(bundle.invoice) ? collectCanonicalFields(bundle.invoice as Record<string, unknown>) : bundle.invoice ?? undefined)

  const normalizedCmr: CanonicalGroupRecord | undefined = cmrGeneral
    ?? (bundle.cmr && isRecord(bundle.cmr) ? collectCanonicalFields(bundle.cmr as Record<string, unknown>) : bundle.cmr ?? undefined)

  const normalizedUb04: CanonicalGroupRecord | undefined = bundle.ub04 && isRecord(bundle.ub04)
    ? collectCanonicalFields(bundle.ub04 as Record<string, unknown>)
    : bundle.ub04 ?? undefined

  const fallbackInvoiceLineItems = (bundle as Record<string, unknown>).invoiceLineItems
  const normalizedInvoiceLineItems = facilityInvoiceLineItems 
    ?? (Array.isArray(fallbackInvoiceLineItems) ? fallbackInvoiceLineItems : null)

  return {
    ...bundle,
    documentCategories: bundle.documentCategories ?? [],
    documentTypes: bundle.documentTypes ?? [],
    reasoningNotes,
    notes: reasoningNotes,
    invoice: normalizedInvoice ?? null,
    invoiceLineItems: normalizedInvoiceLineItems,
    cmr: normalizedCmr ?? null,
    ub04: normalizedUb04 ?? null,
    ub04LineItems: normalizedUb04LineItems ?? null,
  }
}

const normalizeHistoryDetail = (detail: JobHistoryDetail): JobHistoryDetail => {
  const canonical = normalizeCanonicalBundle(detail.canonical)
  return {
    ...detail,
    canonical,
    pages: detail.pages.map(normalizePage),
  }
}

export async function uploadDocument(file: File): Promise<UploadResponse> {
  const formData = new FormData()
  formData.append('file', file)

  const response = await fetch(buildUrl('/api/upload'), {
    method: 'POST',
    body: formData
  })

  return handleResponse<UploadResponse>(response)
}

export async function fetchJobStatus(jobId: string): Promise<JobStatus> {
  const response = await fetch(buildUrl(`/api/jobs/${jobId}/status`), {
    headers: jsonHeaders
  })

  return handleResponse<JobStatus>(response)
}

export async function fetchPageResult(
  jobId: string,
  pageNumber: number
): Promise<PageExtraction> {
  const response = await fetch(buildUrl(`/api/jobs/${jobId}/pages/${pageNumber}`), {
    headers: jsonHeaders
  })

  const page = await handleResponse<PageExtraction>(response)
  return normalizePage(page)
}

export async function fetchAllPages(jobId: string): Promise<PageExtraction[]> {
  const status = await fetchJobStatus(jobId)
  const totalPages = status.totalPages || 0

  if (totalPages === 0) {
    return []
  }

  const pages = await Promise.all(
    Array.from({ length: totalPages }, (_, index) => fetchPageResult(jobId, index + 1))
  )

  return pages.sort((a, b) => a.pageNumber - b.pageNumber)
}

export async function fetchAggregatedResults(jobId: string): Promise<AggregatedResults> {
  const response = await fetch(buildUrl(`/api/jobs/${jobId}/aggregated`), {
    headers: jsonHeaders
  })

  return handleResponse<AggregatedResults>(response)
}

export async function fetchJobHistory(): Promise<JobHistorySummary[]> {
  const response = await fetch(buildUrl('/api/history/jobs'), {
    headers: jsonHeaders
  })

  const data = await handleResponse<{ jobs: JobHistorySummary[] }>(response)
  return data.jobs
}

export async function fetchJobHistoryDetail(jobId: string): Promise<JobHistoryDetail> {
  const response = await fetch(buildUrl(`/api/history/jobs/${jobId}`), {
    headers: jsonHeaders
  })

  const detail = await handleResponse<JobHistoryDetail>(response)
  return normalizeHistoryDetail(detail)
}

export async function fetchCanonicalBundle(jobId: string): Promise<CanonicalBundleResponse> {
  const response = await fetch(buildUrl(`/api/jobs/${jobId}/canonical`), {
    headers: jsonHeaders,
  })

  const payload = await handleResponse<CanonicalBundleResponse>(response)
  return {
    ...payload,
    canonical: normalizeCanonicalBundle(payload.canonical) ?? {
      documentCategories: [],
      documentTypes: [],
      reasoningNotes: [],
      notes: [],
    },
    documentCategories: payload.documentCategories ?? payload.canonical?.documentCategories ?? [],
    documentTypes: payload.documentTypes ?? payload.canonical?.documentTypes ?? [],
    pageCategories: payload.pageCategories ?? {},
    pageClassifications: payload.pageClassifications ?? [],
  }
}

export async function fetchDashboardMetrics(): Promise<DashboardMetrics> {
  const response = await fetch(buildUrl('/api/history/metrics'), {
    headers: jsonHeaders
  })

  return handleResponse<DashboardMetrics>(response)
}

export async function fetchLowConfidenceFields(limit = 50, jobId?: string): Promise<LowConfidenceField[]> {
  const params = new URLSearchParams({ limit: String(limit) })
  if (jobId) {
    params.set('jobId', jobId)
  }
  const response = await fetch(buildUrl(`/api/history/low-confidence?${params.toString()}`), {
    headers: jsonHeaders
  })

  return handleResponse<LowConfidenceField[]>(response)
}

export async function deleteJobHistory(jobId: string): Promise<void> {
  const response = await fetch(buildUrl(`/api/history/jobs/${jobId}`), {
    method: 'DELETE',
    headers: jsonHeaders
  })

  if (response.status === 204) {
    return
  }

  if (!response.ok) {
    let detail = response.statusText
    try {
      const data = await response.json()
      detail = (data as { detail?: string }).detail ?? detail
    } catch (error) {
      void error
    }
    throw new Error(detail || `Request failed with status ${response.status}`)
  }
}

export async function savePageEdits(jobId: string, payload: SaveEditsRequest): Promise<SaveEditsResponse> {
  const response = await fetch(buildUrl(`/api/history/jobs/${jobId}/edits`), {
    method: 'POST',
    headers: jsonHeaders,
    body: JSON.stringify(payload)
  })

  return handleResponse<SaveEditsResponse>(response)
}
