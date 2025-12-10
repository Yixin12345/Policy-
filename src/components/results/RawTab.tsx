import type { PageExtraction } from '../../types/extraction'

type RawTabProps = {
  page?: PageExtraction
  isLoading: boolean
}

const RawTab = ({ page, isLoading }: RawTabProps) => {
  if (isLoading) {
    return (
      <div className="h-full animate-pulse rounded-lg bg-slate-100" />
    )
  }

  if (!page) {
    return (
      <div className="rounded-lg border border-dashed border-slate-200 bg-slate-50 px-4 py-6 text-center text-sm text-slate-500">
        Raw JSON preview appears once extraction finishes for this page.
      </div>
    )
  }

  return (
    <div className="space-y-3">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
        Page {page.pageNumber} JSON
      </h3>
      <pre className="max-h-full overflow-auto rounded-lg border border-slate-200 bg-slate-900 p-4 text-xs text-slate-100">
        {JSON.stringify(page, null, 2)}
      </pre>
    </div>
  )
}

export default RawTab
