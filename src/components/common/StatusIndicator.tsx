import type { JobStatus } from '../../types/extraction'

type StatusIndicatorProps = {
  status?: JobStatus
  isLoading?: boolean
  overrideLabel?: string
  overrideColor?: string
}

const stateCopy: Record<JobStatus['state'], string> = {
  idle: 'Idle',
  queued: 'Queued',
  running: 'Processing',
  completed: 'Completed',
  partial: 'Partial',
  error: 'Error'
}

const StatusIndicator = ({ status, isLoading = false, overrideLabel, overrideColor }: StatusIndicatorProps) => {
  if (isLoading) {
    return (
      <div className="flex items-center gap-2 text-sm text-slate-500">
        <span className="inline-flex h-2.5 w-2.5 animate-pulse rounded-full bg-brand-400" />
        Uploading...
      </div>
    )
  }

  if (!status) {
    return (
      <div className="text-sm text-slate-500">No document uploaded</div>
    )
  }

  const progress = `${status.processedPages}/${status.totalPages}`
  const label = overrideLabel ?? stateCopy[status.state]
  const documentTypes = status.documentTypes && status.documentTypes.length > 0
    ? status.documentTypes
    : status.documentType
      ? [status.documentType]
      : []

  return (
    <div className="flex flex-col gap-1 text-sm text-slate-600">
      <div className="flex items-center gap-3">
        <div className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5">
          <span
            className="inline-flex h-2.5 w-2.5 rounded-full"
            style={{
              backgroundColor: overrideColor
                ?? (status.state === 'completed'
                  ? '#16a34a'
                  : status.state === 'error'
                    ? '#dc2626'
                    : '#64748b')
            }}
          />
          <span>{label}</span>
        </div>
        <span className="text-slate-500">{progress} pages processed</span>
      </div>
      {documentTypes.length > 0 ? (
        <div className="flex flex-wrap items-center gap-1 text-xs text-slate-500">
          <span className="uppercase tracking-wide text-slate-400">Doc type</span>
          {documentTypes.map((type) => (
            <span key={type} className="inline-flex items-center rounded-full bg-brand-50 px-2 py-0.5 text-xs font-semibold uppercase tracking-wide text-brand-600">
              {type}
            </span>
          ))}
        </div>
      ) : null}
    </div>
  )
}

export default StatusIndicator
