import clsx from 'clsx'
import type {
  CanonicalBundle,
  CanonicalSelectPayload,
  CanonicalValue,
  CanonicalValueSource,
  Ub04LineItemTable,
  PageClassification,
} from '../../types/extraction'
import { collectCanonicalFields, findPagesForSources } from '../../utils/canonical'

type CanonicalTabProps = {
  canonical?: CanonicalBundle | null
  documentType?: string | null
  documentTypes?: string[]
  documentCategories?: string[]
  isLoading: boolean
  pageClassifications?: PageClassification[]
  onSelectValue?: (payload: CanonicalSelectPayload | null) => void
}

const formatLabel = (key: string) =>
  key
    .replace(/([A-Z])/g, ' $1')
    .replace(/_/g, ' ')
    .replace(/\s+/g, ' ')
    .replace(/^./, (char) => char.toUpperCase())

const formatConfidence = (confidence?: number | null) => {
  if (confidence === null || confidence === undefined) {
    return undefined
  }
  return `${Math.round(confidence * 100)}%`
}

const formatSources = (sources?: CanonicalValueSource[]) => {
  if (!sources || sources.length === 0) {
    return undefined
  }
  const pages = Array.from(new Set(sources.map((source) => source.page).filter((page): page is number => page !== undefined)))
  if (pages.length === 0) {
    return undefined
  }
  return `Pg ${pages.join(', ')}`
}

const renderCanonicalValue = (value?: CanonicalValue | null, isInteractive = false) => {
  if (!value) {
    return (
      <span className="text-slate-400">—</span>
    )
  }
  const displayValue =
    value.value === null || value.value === undefined || value.value === ''
      ? '—'
      : String(value.value)
  const confidenceLabel = formatConfidence(value.confidence)
  const sourcesLabel = formatSources(value.sources)
  return (
    <div className="flex flex-col gap-1">
      <span className="text-sm font-medium text-slate-700">{displayValue}</span>
      {(confidenceLabel || sourcesLabel || isInteractive) && (
        <div className="flex flex-wrap items-center gap-2 text-[0.65rem] uppercase tracking-wide text-slate-400">
          {confidenceLabel ? <span>Conf {confidenceLabel}</span> : null}
          {sourcesLabel ? <span>{sourcesLabel}</span> : null}
          {isInteractive ? <span className="text-brand-500">View in PDF</span> : null}
        </div>
      )}
    </div>
  )
}

const renderKeyValueList = (
  values: Record<string, CanonicalValue | null | undefined>,
  section: CanonicalSelectPayload['section'],
  onSelect?: (payload: CanonicalSelectPayload | null) => void,
) => {
  const entries = Object.entries(values)
  if (entries.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-slate-200 bg-slate-50 px-3 py-4 text-sm text-slate-500">
        No mapped values yet.
      </div>
    )
  }

  return (
    <dl className="grid gap-3 sm:grid-cols-2">
      {entries.map(([key, value]) => {
        const hasSources = Boolean(value?.sources && value.sources.length > 0 && onSelect)
        const handleSelect = () => {
          if (hasSources && onSelect && value) {
            onSelect({
              label: formatLabel(key),
              value,
              sources: value.sources,
              section,
            })
          }
        }

        return (
          <div
            key={key}
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
            <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">{formatLabel(key)}</dt>
            <dd>{renderCanonicalValue(value ?? undefined, hasSources)}</dd>
          </div>
        )
      })}
    </dl>
  )
}

const renderLineItems = (
  lineItems: Array<Record<string, unknown>>,
  onSelect?: (payload: CanonicalSelectPayload | null) => void,
  section: CanonicalSelectPayload['section'] = 'facility_invoice',
) => {
  if (!lineItems || lineItems.length === 0) {
    return null
  }

  const normalizedItems = lineItems.map((item) => collectCanonicalFields(item as Record<string, unknown>))
  const allKeys = Array.from(new Set(normalizedItems.flatMap((item) => Object.keys(item))))
  if (allKeys.length === 0) {
    return null
  }

  return (
    <div className="space-y-2">
      {normalizedItems.map((item, index) => {
        const lineSources = Object.values(item)
          .flatMap((value) => value?.sources ?? [])
          .filter((source): source is CanonicalValueSource => Boolean(source))
        const pageSummary = findPagesForSources(lineSources)

        return (
          <div key={index} className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
            <div className="mb-3 flex items-center justify-between text-xs font-semibold uppercase tracking-wide text-slate-500">
              <span>Line item {index + 1}</span>
              {pageSummary.length > 0 ? (
                <span className="text-[0.65rem] text-slate-400">{pageSummary.map((page) => `Pg ${page}`).join(', ')}</span>
              ) : null}
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              {allKeys.map((key) => {
                const value = item[key]
                const hasSources = Boolean(value?.sources && value.sources.length > 0 && onSelect)
                const handleSelect = () => {
                  if (hasSources && onSelect && value) {
                    onSelect({
                      label: `${formatLabel(key)} (line ${index + 1})`,
                      value,
                      sources: value.sources,
                      section,
                    })
                  }
                }

                return (
                  <div
                    key={key}
                    className={clsx(
                      'rounded border border-slate-100 bg-slate-50 p-3 transition',
                      hasSources ? 'cursor-pointer hover:border-brand-300 hover:bg-white hover:shadow-sm' : '',
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
                    <div className="text-[0.65rem] font-semibold uppercase tracking-wide text-slate-500">
                      {formatLabel(key)}
                    </div>
                    {renderCanonicalValue(value, hasSources)}
                  </div>
                )
              })}
            </div>
          </div>
        )
      })}
    </div>
  )
}

const renderUb04LineItemTables = (
  tables: Ub04LineItemTable[],
  onSelect?: (payload: CanonicalSelectPayload | null) => void,
) => {
  if (!tables || tables.length === 0) {
    return null
  }

  return (
    <div className="space-y-4">
      {tables.map((table, index) => {
        const tableKey = table.tableId ?? `ub04-line-table-${index}`
        const headers = Array.isArray(table.headers) ? table.headers : []
        const headerLabels = headers
          .map((header) => header?.label ?? header?.key ?? undefined)
          .filter((label): label is string => Boolean(label))
        const tableConfidence = formatConfidence(table.confidence)
        const tablePages = findPagesForSources(table.sources)
        const items = Array.isArray(table.items) ? table.items : []

        return (
          <div key={tableKey} className="rounded-lg border border-slate-200 bg-slate-50 p-4 shadow-sm">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
              <span>Line items table {index + 1}</span>
              {(tableConfidence || tablePages.length > 0) ? (
                <div className="flex flex-wrap items-center gap-2 text-[0.65rem] uppercase tracking-wide text-slate-400">
                  {tableConfidence ? <span>Conf {tableConfidence}</span> : null}
                  {tablePages.length > 0 ? <span>{tablePages.map((page) => `Pg ${page}`).join(', ')}</span> : null}
                </div>
              ) : null}
            </div>
            {headerLabels.length > 0 ? (
              <div className="mb-3 flex flex-wrap items-center gap-2 text-[0.65rem] uppercase tracking-wide text-slate-400">
                {headerLabels.map((label, headerIndex) => (
                  <span key={`${tableKey}-header-${headerIndex}`} className="rounded-full bg-white px-2 py-1 text-slate-500 shadow-sm">
                    {label}
                  </span>
                ))}
              </div>
            ) : null}
            {renderLineItems(items as Array<Record<string, unknown>>, onSelect, 'ub04')}
          </div>
        )
      })}
    </div>
  )
}

const CanonicalTab = ({
  canonical,
  documentType,
  documentTypes,
  documentCategories,
  isLoading,
  pageClassifications,
  onSelectValue,
}: CanonicalTabProps) => {
  if (isLoading) {
    return <div className="h-full animate-pulse rounded-lg bg-slate-100" />
  }

  const effectiveTypes =
    (canonical?.documentCategories?.length ? canonical.documentCategories : undefined) ??
    (documentCategories && documentCategories.length ? documentCategories : undefined) ??
    (canonical?.documentTypes?.length ? canonical.documentTypes : undefined) ??
    (documentTypes && documentTypes.length ? documentTypes : undefined) ??
    (documentType ? [documentType] : [])
  const invoiceRaw = canonical?.invoice as Record<string, CanonicalValue | null | undefined> | undefined
  const invoiceFields: Record<string, CanonicalValue | null | undefined> | undefined = invoiceRaw
    ? Object.fromEntries(Object.entries(invoiceRaw))
    : undefined

  const explicitLineItems = (() => {
    const bundleWithItems = canonical as {
      invoiceLineItems?: Array<Record<string, unknown>>
      facilityInvoice?: { lineItems?: Array<Record<string, unknown>> }
    }
    if (bundleWithItems?.invoiceLineItems && Array.isArray(bundleWithItems.invoiceLineItems)) {
      return bundleWithItems.invoiceLineItems
    }
    if (bundleWithItems?.facilityInvoice?.lineItems && Array.isArray(bundleWithItems.facilityInvoice.lineItems)) {
      return bundleWithItems.facilityInvoice.lineItems
    }
    return undefined
  })()

  let invoiceLineItems: Array<Record<string, unknown>> = Array.isArray(explicitLineItems) ? explicitLineItems : []

  if (invoiceFields && 'Line items (Boxes 42–47)' in invoiceFields) {
    const lineEntry = invoiceFields['Line items (Boxes 42–47)']
    const rawValue = lineEntry && typeof lineEntry === 'object' ? (lineEntry as CanonicalValue).value : undefined
    if (!invoiceLineItems.length && rawValue && typeof rawValue === 'object' && 'items' in (rawValue as Record<string, unknown>)) {
      const items = (rawValue as { items?: Array<Record<string, unknown>> }).items
      if (Array.isArray(items)) {
        invoiceLineItems = items
      }
    }
    delete invoiceFields['Line items (Boxes 42–47)']
  }

  const cmrRaw = canonical?.cmr as Record<string, CanonicalValue | null | undefined> | undefined
  const ub04Raw = canonical?.ub04 as Record<string, CanonicalValue | null | undefined> | undefined
  const ub04Fields: Record<string, CanonicalValue | null | undefined> | undefined = ub04Raw
    ? Object.fromEntries(Object.entries(ub04Raw))
    : undefined
  const rawUb04LineItems = (canonical as { ub04LineItems?: Ub04LineItemTable[] | null } | undefined)?.ub04LineItems
  let ub04LineItems: Ub04LineItemTable[] = Array.isArray(rawUb04LineItems) ? rawUb04LineItems : []

  if (ub04Fields && 'Line items (Boxes 42–47)' in ub04Fields) {
    const lineEntry = ub04Fields['Line items (Boxes 42–47)']
    const rawValue = lineEntry && typeof lineEntry === 'object' ? (lineEntry as CanonicalValue).value : undefined

    let structuredValue: unknown = rawValue
    if (typeof structuredValue === 'string') {
      try {
        structuredValue = JSON.parse(structuredValue)
      } catch {
        structuredValue = undefined
      }
    }

    if (!ub04LineItems.length && structuredValue && typeof structuredValue === 'object' && 'items' in (structuredValue as Record<string, unknown>)) {
      const legacyTable = structuredValue as Record<string, unknown>
      const legacyItems = (legacyTable.items ?? []) as Array<Record<string, unknown>>
      ub04LineItems = [
        {
          tableId: typeof legacyTable.tableId === 'string' ? legacyTable.tableId : undefined,
          headers: Array.isArray(legacyTable.headers)
            ? (legacyTable.headers as Ub04LineItemTable['headers'])
            : undefined,
          items: legacyItems,
          sources: lineEntry?.sources,
          confidence: lineEntry?.confidence ?? undefined,
        },
      ]
    }
    delete ub04Fields['Line items (Boxes 42–47)']
  }
  const notes = canonical?.reasoningNotes ?? canonical?.notes ?? []
  const hasInvoiceContent = Boolean(invoiceFields && Object.keys(invoiceFields).length > 0) || invoiceLineItems.length > 0
  const hasCmrContent = Boolean(cmrRaw && Object.keys(cmrRaw).length > 0)
  const hasUb04Content = Boolean(ub04Fields && Object.keys(ub04Fields).length > 0) || ub04LineItems.length > 0

  const pageTypeHints = pageClassifications?.filter((hint) => hint.label)

  if (!canonical && effectiveTypes.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-slate-200 bg-slate-50 px-4 py-6 text-center text-sm text-slate-500">
        Canonical mapping will appear once processing finishes for this document.
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col gap-4 overflow-auto pr-1">
      <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Document classification</h3>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          {effectiveTypes.length > 0 ? (
            effectiveTypes.map((type) => (
              <span
                key={type}
                className="inline-flex items-center rounded-full bg-brand-50 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-brand-600"
              >
                {type}
              </span>
            ))
          ) : (
            <span className="text-sm text-slate-500">No classification yet.</span>
          )}
        </div>
        {pageTypeHints && pageTypeHints.length > 0 ? (
          <div className="mt-3">
            <h4 className="text-[0.65rem] font-semibold uppercase tracking-wide text-slate-400">Page hints</h4>
            <ul className="mt-1 grid gap-1 text-xs text-slate-500 sm:grid-cols-2">
              {pageTypeHints.map((hint) => (
                <li key={hint.page} className="rounded bg-slate-50 px-2 py-1">
                  Pg {hint.page}: {hint.label}
                  {hint.confidence !== undefined ? ` (${formatConfidence(hint.confidence)})` : ''}
                </li>
              ))}
            </ul>
          </div>
        ) : null}
        {canonical?.generatedAt ? (
          <p className="mt-3 text-[0.65rem] uppercase tracking-wide text-slate-400">
            Generated {new Date(canonical.generatedAt).toLocaleString()}
          </p>
        ) : null}
      </section>

      {invoiceFields ? (
        <section className="space-y-4 rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <header>
            <h3 className="text-sm font-semibold text-slate-700">Invoice</h3>
            <p className="text-xs text-slate-500">Canonical fields mapped for invoice-style documents.</p>
          </header>
          {Object.keys(invoiceFields).length > 0 ? renderKeyValueList(invoiceFields, 'facility_invoice', onSelectValue) : (
            <div className="rounded-lg border border-dashed border-slate-200 bg-slate-50 px-3 py-4 text-sm text-slate-500">
              No general invoice fields mapped yet.
            </div>
          )}
          {invoiceLineItems.length > 0 ? (
            <div>
              <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Line items</h4>
              {renderLineItems(invoiceLineItems)}
            </div>
          ) : null}
        </section>
      ) : null}

      {cmrRaw && Object.keys(cmrRaw).length > 0 ? (
        <section className="space-y-3 rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <header>
            <h3 className="text-sm font-semibold text-slate-700">CMR form</h3>
            <p className="text-xs text-slate-500">Canonical fields mapped from care management reports.</p>
          </header>
          {renderKeyValueList(cmrRaw, 'cmr_form', onSelectValue)}
        </section>
      ) : null}

      {hasUb04Content ? (
        <section className="space-y-4 rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <header>
            <h3 className="text-sm font-semibold text-slate-700">UB-04</h3>
            <p className="text-xs text-slate-500">Canonical fields mapped from UB-04 claim forms.</p>
          </header>
          {ub04Fields && Object.keys(ub04Fields).length > 0 ? (
            renderKeyValueList(ub04Fields, 'ub04', onSelectValue)
          ) : ub04LineItems.length === 0 ? (
            <div className="rounded-lg border border-dashed border-slate-200 bg-slate-50 px-3 py-4 text-sm text-slate-500">
              No UB-04 fields mapped yet.
            </div>
          ) : null}
          {ub04LineItems.length > 0 ? (
            <div>
              <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Line items</h4>
              {renderUb04LineItemTables(ub04LineItems, onSelectValue)}
            </div>
          ) : null}
        </section>
      ) : null}

      {notes.length > 0 ? (
        <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Model notes</h3>
          <ul className="mt-2 list-disc space-y-1 pl-4 text-sm text-slate-600">
            {notes.map((note, index) => (
              <li key={`${note}-${index}`}>{note}</li>
            ))}
          </ul>
        </section>
      ) : null}

      {!hasInvoiceContent && !hasCmrContent && !hasUb04Content && notes.length === 0 ? (
        <div className="rounded-lg border border-dashed border-slate-200 bg-slate-50 px-4 py-6 text-center text-sm text-slate-500">
          Canonical bundle is empty for this document.
        </div>
      ) : null}
    </div>
  )
}

export default CanonicalTab
