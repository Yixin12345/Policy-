export type BoundingBox = {
  x: number
  y: number
  width: number
  height: number
}

export type FieldExtraction = {
  id: string
  page: number
  name: string
  value: string
  confidence: number
  bbox?: BoundingBox
  sourceType?: 'text' | 'checkbox' | 'signature' | 'table-cell'
  revised?: boolean
  originalValue?: string
}

export type CanonicalValueSource = {
  page?: number
  fieldId?: string
  tableId?: string
  column?: string
}

export type CanonicalValue = {
  value: unknown
  confidence?: number | null
  sources?: CanonicalValueSource[]
}

export type CanonicalGroupRecord = Record<string, CanonicalValue | null | undefined>

export type Ub04LineItemHeader = {
  columnIndex?: number
  label?: string
  key?: string | null
}

export type Ub04LineItemTable = {
  tableId?: string
  confidence?: number | null
  headers?: Ub04LineItemHeader[]
  items?: Array<Record<string, unknown>>
  sources?: CanonicalValueSource[]
}

export type CanonicalBundle = {
  generatedAt?: string
  schemaVersion?: string
  documentCategories?: string[]
  documentTypes?: string[]
  reasoningNotes?: string[]
  notes?: string[]
  identityBlocks?: Array<Record<string, unknown>> | null
  sourceMap?: Record<string, unknown> | null
  policyConversion?: CanonicalGroupRecord | null
  [key: string]: unknown
}

export type CanonicalSection = 'policy_conversion' | 'unknown'

export type CanonicalSelectPayload = {
  label: string
  value?: CanonicalValue | null
  sources?: CanonicalValueSource[]
  section: CanonicalSection
}

export type MappingTrace = {
  prompt?: Record<string, unknown>
  response?: string
  model?: string
  [key: string]: unknown
}

export type CanonicalBundleResponse = {
  jobId: string
  canonical: CanonicalBundle
  trace?: MappingTrace | null
  documentCategories?: string[]
  documentTypes?: string[]
  pageCategories?: Record<number, string>
  pageClassifications?: PageClassification[]
}

export type PageClassification = {
  page: number
  label?: string
  confidence?: number
  reasons?: string[]
}

export type TableColumn = {
  key: string
  header: string
  type?: 'string' | 'number' | 'date'
  confidence?: number
}

export type TableCell = {
  value: string
  confidence?: number
  bbox?: BoundingBox
}

export type TableExtraction = {
  id: string
  page: number
  caption?: string
  confidence?: number
  columns: TableColumn[]
  rows: TableCell[][]
  bbox?: BoundingBox
  normalized?: boolean
  tableGroupId?: string
  continuationOf?: string
  inferredHeaders?: boolean
  rowStartIndex?: number
}

export type PageExtraction = {
  pageNumber: number
  status: 'pending' | 'processing' | 'completed' | 'error'
  fields: FieldExtraction[]
  tables: TableExtraction[]
  imageUrl?: string
  markdownText?: string
  errorMessage?: string
  rotationApplied?: number
  documentTypeHint?: string
  documentTypeConfidence?: number
}

export type HighlightRegion = {
  id: string
  page: number
  bbox: BoundingBox
  section: CanonicalSection
  label: string
}

export type JobStatus = {
  jobId: string
  totalPages: number
  processedPages: number
  state: 'idle' | 'queued' | 'running' | 'completed' | 'partial' | 'error'
  errors?: Array<{ page: number; message: string }>
  startedAt?: string
  finishedAt?: string
  documentType?: string | null
  documentTypes?: string[]
}

export type AggregatedField = {
  canonicalName: string
  pages: number[]
  values: Array<{ page: number; value: string; confidence: number }>
  bestValue: string
  confidenceStats: {
    min: number
    max: number
    avg: number
  }
}

export type AggregatedResults = {
  jobId: string
  fields: AggregatedField[]
}

export type UploadResponse = {
  jobId: string
}

export type ExtractionJob = {
  status: JobStatus
  pages: PageExtraction[]
  aggregated: AggregatedResults
}

export type JobSummaryMetrics = {
  totalPages: number
  totalFields: number
  totalTables: number
  totalProcessingMs?: number
  startedAt?: string
  finishedAt?: string
}

export type JobHistorySummary = {
  jobId: string
  documentName: string
  documentType?: string
  totalPages: number
  totalFields: number
  totalTables: number
  totalProcessingMs?: number
  startedAt?: string
  finishedAt?: string
  lastModified?: string
  status: JobStatus['state']
  confidenceBuckets: number[]
  lowConfidenceCount: number
}

export type DashboardWindowMetrics = {
  totalJobs: number
  totalPages: number
  totalFields: number
  totalTables: number
  totalProcessingMs?: number
}

export type DashboardMetrics = {
  week: DashboardWindowMetrics
  month: DashboardWindowMetrics
  year: DashboardWindowMetrics
}

export type JobHistoryDetail = {
  jobId: string
  documentName: string
  summary: JobSummaryMetrics
  status: JobStatus
  pages: PageExtraction[]
  aggregated: AggregatedResults
  metadata: Record<string, unknown>
  documentType?: string
  canonical?: CanonicalBundle | null
  mappingTrace?: MappingTrace | null
  pageClassifications?: PageClassification[]
}

export type LowConfidenceField = {
  jobId: string
  documentName: string
  page: number
  name: string
  value: string
  confidence: number
}

export type FieldUpdatePayload = {
  fieldId?: string
  name: string
  value: string
  confidence?: number
}

export type TableCellUpdatePayload = {
  tableId: string
  row: number
  column: number
  value: string
}

export type SaveEditsRequest = {
  page: number
  fields: FieldUpdatePayload[]
  tableCells: TableCellUpdatePayload[]
}

export type SaveEditsResponse = {
  jobId: string
  page: number
  updatedFields: FieldExtraction[]
  updatedTables: TableExtraction[]
}
