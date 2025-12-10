import clsx from 'clsx'
import type { CanonicalBundle, CanonicalSelectPayload, CanonicalValue, CanonicalValueSource, PageClassification } from '../../types/extraction'

type CanonicalTabProps = {
  canonical?: CanonicalBundle | null
  documentType?: string | null
  documentTypes?: string[]
  documentCategories?: string[]
  isLoading: boolean
  pageClassifications?: PageClassification[]
  onSelectValue?: (payload: CanonicalSelectPayload | null) => void
}

const formatConfidence = (confidence?: number | null) => {
  if (confidence === null || confidence === undefined) return undefined
  return `${Math.round(confidence * 100)}%`
}

const formatSources = (sources?: CanonicalValueSource[]) => {
  if (!sources || sources.length === 0) return undefined
  const pages = Array.from(
    new Set(sources.map((source) => source.page).filter((page): page is number => page !== undefined)),
  )
  if (pages.length === 0) return undefined
  return `Pg ${pages.join(', ')}`
}

const renderValue = (value?: CanonicalValue | null, interactive = false) => {
  if (!value) {
    return <span className="text-slate-400">not provided</span>
  }
  const display =
    value.value === null || value.value === undefined || value.value === '' ? 'not provided' : String(value.value)
  const confidenceLabel = formatConfidence(value.confidence)
  const sourcesLabel = formatSources(value.sources)
  return (
    <div className="flex flex-col gap-1">
      <span className="text-sm font-medium text-slate-800">{display}</span>
      {(confidenceLabel || sourcesLabel || interactive) && (
        <div className="flex flex-wrap items-center gap-2 text-[0.65rem] uppercase tracking-wide text-slate-400">
          {confidenceLabel ? <span>Conf {confidenceLabel}</span> : null}
          {sourcesLabel ? <span>{sourcesLabel}</span> : null}
          {interactive ? <span className="text-brand-500">View in PDF</span> : null}
        </div>
      )}
    </div>
  )
}

export function CanonicalTab({
  canonical,
  isLoading,
  documentCategories,
  documentTypes,
  documentType,
  onSelectValue,
}: CanonicalTabProps) {
  if (isLoading) {
    return <div className="rounded-lg border border-dashed border-slate-200 bg-slate-50 px-4 py-6 text-sm text-slate-500">Loading canonical mapping…</div>
  }

  const policyConversion = canonical?.policyConversion as Record<string, CanonicalValue | null | undefined> | undefined
  const effectiveTypes = (documentTypes && documentTypes.length > 0
    ? documentTypes
    : documentCategories && documentCategories.length > 0
      ? documentCategories
      : documentType
        ? [documentType]
        : [])
  const entries = policyConversion ? Object.entries(policyConversion) : []

  if (!canonical && entries.length === 0) {
    return <div className="rounded-lg border border-dashed border-slate-200 bg-slate-50 px-4 py-6 text-sm text-slate-500">No canonical mapping generated yet.</div>
  }

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Document type</div>
          <div className="text-sm text-slate-800">{effectiveTypes.length ? effectiveTypes.join(', ') : 'policy_conversion'}</div>
        </div>
        {canonical?.generatedAt ? (
          <div className="text-xs text-slate-500">Generated {new Date(canonical.generatedAt).toLocaleString()}</div>
        ) : null}
      </header>

      <div className="grid gap-3 sm:grid-cols-2">
        {entries.map(([label, value]) => {
          const hasSources = Boolean(value?.sources && value.sources.length > 0 && onSelectValue)
          const handleSelect = () => {
            if (hasSources && onSelectValue && value) {
              onSelectValue({
                label,
                value,
                sources: value.sources,
                section: 'unknown',
              })
            }
          }
          return (
            <div
              key={label}
              className={clsx(
                'rounded-lg border border-slate-200 bg-white p-3 shadow-sm transition',
                hasSources ? 'cursor-pointer hover:border-brand-300 hover:shadow' : '',
              )}
              onClick={handleSelect}
              onKeyDown={(event) => {
                if (event.key === 'Enter' || event.key === ' ') {
                  event.preventDefault()
                  handleSelect()
                }
              }}
              role={hasSources ? 'button' : undefined}
              tabIndex={hasSources ? 0 : undefined}
            >
              <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</div>
              {renderValue(value ?? undefined, hasSources)}
            </div>
          )
        })}
      </div>
    </div>
  )
}

export default CanonicalTab
