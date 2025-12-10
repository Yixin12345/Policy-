import type { AggregatedResults } from '../../types/extraction'

type SummaryTabProps = {
  aggregated?: AggregatedResults
}

const SummaryTab = ({ aggregated }: SummaryTabProps) => {
  if (!aggregated || aggregated.fields.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-slate-200 bg-slate-50 px-4 py-6 text-center text-sm text-slate-500">
        Upload a PDF or Markdown document to view aggregated results.
      </div>
    )
  }

  return (
    <div className="space-y-4 overflow-y-auto">
      <section aria-label="Aggregated Fields" className="space-y-3">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
          Aggregated Fields
        </h3>
        <div className="space-y-2">
          {aggregated.fields.map((field) => (
            <div
              key={field.canonicalName}
              className="rounded-lg border border-slate-200 bg-white p-3 shadow-sm"
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-slate-700">
                    {field.canonicalName}
                  </p>
                  <p className="text-sm text-slate-600 whitespace-pre-wrap">
                    {field.bestValue}
                  </p>
                </div>
                <div className="rounded-md bg-slate-100 px-2 py-1 text-xs font-medium text-slate-600">
                  Avg conf: {(field.confidenceStats.avg * 100).toFixed(0)}%
                </div>
              </div>
              <p className="mt-2 text-xs text-slate-500">
                Seen on pages {field.pages.join(', ')}
              </p>
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}

export default SummaryTab
