import ConfidenceBadge from '../common/ConfidenceBadge'
import type { FieldExtraction } from '../../types/extraction'

type FieldsTabProps = {
  pageFields?: FieldExtraction[]
  isLoading: boolean
  isEditing?: boolean
  getFieldValue?: (field: FieldExtraction, index: number) => string
  onFieldChange?: (field: FieldExtraction, index: number, value: string) => void
}

const FieldsTab = ({ pageFields, isLoading, isEditing = false, getFieldValue, onFieldChange }: FieldsTabProps) => {
  if (isLoading) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 4 }).map((_, index) => (
          <div
            key={index}
            className="h-16 animate-pulse rounded-lg bg-slate-100"
          />
        ))}
      </div>
    )
  }

  if (!pageFields || pageFields.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-slate-200 bg-slate-50 px-4 py-6 text-center text-sm text-slate-500">
        Upload a PDF or Markdown document to see extracted fields.
      </div>
    )
  }

  return (
    <div className="space-y-4 overflow-y-auto">
      <section aria-label="Page Fields" className="space-y-3">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
          Fields on this page
        </h3>
        <div className="space-y-2">
          {pageFields.map((field, index) => (
            <div
              key={field.id ?? `${field.name}-${index}`}
              className="rounded-lg border border-slate-200 bg-white p-3 shadow-sm"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1">
                  <p className="text-sm font-semibold text-slate-700">
                    {field.name}
                  </p>
                  {isEditing ? (
                    <textarea
                      value={getFieldValue ? getFieldValue(field, index) : field.value}
                      onChange={(event) => onFieldChange?.(field, index, event.target.value)}
                      rows={3}
                      className="mt-2 w-full rounded-md border border-slate-200 px-3 py-2 text-sm text-slate-700 shadow-sm focus:border-brand-400 focus:outline-none focus:ring focus:ring-brand-200"
                    />
                  ) : (
                    <p className="whitespace-pre-wrap text-sm text-slate-600">
                      {field.value}
                    </p>
                  )}
                  {isEditing && field.originalValue ? (
                    <button
                      type="button"
                      onClick={() => onFieldChange?.(field, index, field.originalValue ?? field.value)}
                      className="mt-2 inline-flex items-center gap-1 text-xs font-semibold text-brand-600 hover:text-brand-700"
                    >
                      Restore original
                    </button>
                  ) : null}
                  {field.originalValue && !isEditing && field.revised ? (
                    <p className="mt-2 text-xs text-slate-400">
                      Original value: {field.originalValue}
                    </p>
                  ) : null}
                </div>
                <ConfidenceBadge score={field.confidence} />
              </div>
              <div className="mt-2 flex flex-wrap items-center justify-between gap-2 text-xs text-slate-500">
                {field.bbox ? (
                  <span>
                    Bounding box: {`x=${Math.round(field.bbox.x)}, y=${Math.round(field.bbox.y)}, w=${Math.round(field.bbox.width)}, h=${Math.round(field.bbox.height)}`}
                  </span>
                ) : (
                  <span aria-hidden="true" />
                )}
                {field.revised && !isEditing ? (
                  <span className="rounded-full bg-amber-50 px-2 py-0.5 text-[11px] font-semibold text-amber-700">
                    Edited
                  </span>
                ) : null}
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}

export default FieldsTab
