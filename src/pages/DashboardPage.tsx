import { useCallback, useMemo, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import AppShell from '../components/layout/AppShell'
import { useHistoryJobs, useHistoryMetrics, useLowConfidenceFields } from '../hooks/useHistoryData'
import { deleteJobHistory } from '../services/apiClient'
import type { JobHistorySummary } from '../types/extraction'
import { useViewerStore } from '../state/viewerStore'
import { CHART_COLORS, STATUS_LABELS, STATUS_BADGE_CLASS, CONFIDENCE_BUCKET_LABELS } from '../core/constants/app.constants'

type SortOption = 'recent' | 'pages-desc' | 'fields-desc' | 'duration-desc'

const SORT_LABELS: Record<SortOption, string> = {
  recent: 'Most recent',
  'pages-desc': 'Pages ↓',
  'fields-desc': 'Fields ↓',
  'duration-desc': 'Processing time ↓'
}

const DashboardPage = () => {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const historyJobsQuery = useHistoryJobs()
  const historyMetricsQuery = useHistoryMetrics()
  const lowConfidenceFieldsQuery = useLowConfidenceFields()

  const jobs = useMemo(() => historyJobsQuery.data ?? [], [historyJobsQuery.data])
  const totalLowConfidenceFields = useMemo(
    () => jobs.reduce((accumulator, job) => accumulator + (job.lowConfidenceCount ?? 0), 0),
    [jobs]
  )

  const confidenceHistogramData = useMemo(() => {
    const aggregate = Array.from({ length: CONFIDENCE_BUCKET_LABELS.length }, () => 0)
    jobs.forEach((job) => {
      if (Array.isArray(job.confidenceBuckets)) {
        for (let index = 0; index < aggregate.length; index += 1) {
          aggregate[index] += job.confidenceBuckets[index] ?? 0
        }
      }
    })
    return CONFIDENCE_BUCKET_LABELS.map((label, index) => ({
      bucket: label,
      count: aggregate[index] ?? 0
    }))
  }, [jobs])

  const setViewerJob = useViewerStore((state) => state.setJobId)

  const [searchTerm, setSearchTerm] = useState('')
  const [statusFilter, setStatusFilter] = useState<'all' | JobHistorySummary['status']>('all')
  const [minPages, setMinPages] = useState('')
  const [maxPages, setMaxPages] = useState('')
  const [sortOption, setSortOption] = useState<SortOption>('recent')
  const [deletingJobId, setDeletingJobId] = useState<string | null>(null)

  const deleteJobMutation = useMutation<void, Error, string>({
    mutationFn: (jobId: string) => deleteJobHistory(jobId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['history', 'jobs'] })
      queryClient.invalidateQueries({ queryKey: ['history', 'metrics'] })
    },
    onError: (error) => {
      window.alert(error.message)
    }
  })

  const handleNewUpload = () => {
    navigate('/workspace')
  }

  const openJob = useCallback(
    (jobId: string, totalPages?: number) => {
      setViewerJob(jobId, totalPages)
      queryClient.invalidateQueries({ queryKey: ['job-status', jobId], exact: true })
      queryClient.invalidateQueries({ queryKey: ['pages', jobId], exact: true })
      queryClient.invalidateQueries({
        predicate: (query) => {
          const key = query.queryKey
          return Array.isArray(key) && key[0] === 'page' && key[1] === jobId
        }
      })
      queryClient.invalidateQueries({ queryKey: ['aggregated', jobId], exact: true })
      queryClient.invalidateQueries({ queryKey: ['history', 'jobs', jobId], exact: true })
      navigate(`/workspace/${jobId}`)
    },
    [navigate, queryClient, setViewerJob]
  )

  const handleOpenJob = (job: JobHistorySummary) => {
    openJob(job.jobId, job.totalPages)
  }

  const parseDate = useCallback((value?: string | null) => {
    if (!value) return undefined
    const asDate = new Date(value)
    return Number.isNaN(asDate.getTime()) ? undefined : asDate
  }, [])

  const formatDateTime = (value?: string | null) => {
    const parsed = parseDate(value)
    return parsed ? parsed.toLocaleString() : '—'
  }

  const formatDuration = (milliseconds?: number | null) => {
    if (!milliseconds) return '—'
    const seconds = Math.floor(milliseconds / 1000)
    if (seconds < 60) return `${seconds}s`
    const minutes = Math.floor(seconds / 60)
    if (minutes < 60) return `${minutes}m`
    const hours = Math.floor(minutes / 60)
    if (hours < 24) return `${hours}h ${minutes % 60}m`
    const days = Math.floor(hours / 24)
    return `${days}d ${hours % 24}h`
  }

  const timelineData = useMemo(() => {
    if (jobs.length === 0) return []
    const entries = jobs
      .map((job) => {
        const marker = parseDate(job.finishedAt ?? job.lastModified ?? job.startedAt)
        return marker
          ? {
              jobId: job.jobId,
              label: marker.toLocaleDateString(undefined, { month: 'short', day: 'numeric' }),
              totalPages: job.totalPages,
              totalFields: job.totalFields,
              totalTables: job.totalTables,
              processingMinutes: job.totalProcessingMs ? Math.round(job.totalProcessingMs / 60000) : 0,
              timestamp: marker.getTime(),
            }
          : undefined
      })
      .filter(Boolean) as Array<{
        jobId: string
        label: string
        totalPages: number
        totalFields: number
        totalTables: number
        processingMinutes: number
        timestamp: number
      }>

    return entries
      .sort((a, b) => a.timestamp - b.timestamp)
      .map((entry, index) => ({ ...entry, cumulativeJobs: index + 1 }))
  }, [jobs, parseDate])

  const statusBreakdown = useMemo(() => {
    if (jobs.length === 0) return []
    const counts: Record<string, number> = {}
    jobs.forEach((job) => {
      counts[job.status] = (counts[job.status] ?? 0) + 1
    })
    return Object.entries(counts).map(([status, count]) => ({ status, count }))
  }, [jobs])

  const formatTimelineTick = useCallback((value: number) => {
    const date = new Date(value)
    return Number.isNaN(date.getTime())
      ? ''
      : date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
  }, [])

  const formatTimelineTooltipLabel = useCallback((value: number) => {
    const date = new Date(value)
    return Number.isNaN(date.getTime()) ? '' : date.toLocaleString()
  }, [])

  const filteredJobs = useMemo(() => {
    const lowerSearch = searchTerm.trim().toLowerCase()
    const min = Number.parseInt(minPages, 10)
    const max = Number.parseInt(maxPages, 10)

    return jobs
      .filter((job) => {
        if (lowerSearch && !job.documentName.toLowerCase().includes(lowerSearch)) {
          return false
        }
        if (statusFilter !== 'all' && job.status !== statusFilter) {
          return false
        }
        if (!Number.isNaN(min) && job.totalPages < min) {
          return false
        }
        if (!Number.isNaN(max) && job.totalPages > max) {
          return false
        }
        return true
      })
      .sort((a, b) => {
        if (sortOption === 'recent') {
          const aTime = parseDate(a.finishedAt ?? a.lastModified)?.getTime() ?? 0
          const bTime = parseDate(b.finishedAt ?? b.lastModified)?.getTime() ?? 0
          return bTime - aTime
        }
        if (sortOption === 'pages-desc') {
          return b.totalPages - a.totalPages
        }
        if (sortOption === 'fields-desc') {
          return b.totalFields - a.totalFields
        }
        const aDuration = a.totalProcessingMs ?? 0
        const bDuration = b.totalProcessingMs ?? 0
        return bDuration - aDuration
      })
  }, [jobs, searchTerm, statusFilter, minPages, maxPages, sortOption, parseDate])

  const handleResetFilters = () => {
    setSearchTerm('')
    setStatusFilter('all')
    setMinPages('')
    setMaxPages('')
    setSortOption('recent')
  }

  const handleDeleteJob = useCallback(
    (jobId: string) => {
      if (!window.confirm('Delete this job from history? This action cannot be undone.')) {
        return
      }
      setDeletingJobId(jobId)
      deleteJobMutation.mutate(jobId, {
        onSettled: () => {
          setDeletingJobId(null)
        }
      })
    },
    [deleteJobMutation]
  )

  return (
    <AppShell>
      <header className="flex h-16 items-center justify-between border-b border-slate-200 bg-white px-6 shadow-sm">
        <div className="flex items-center gap-4">
          <img src="/synechron-logo.png" alt="Synechron logo" className="h-9 w-auto" />
          <div>
            <h1 className="text-xl font-semibold text-brand-600">Recon AI 2.0</h1>
            <p className="text-sm text-slate-500">Visualise throughput, quality, and job health at a glance.</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={handleNewUpload}
            className="rounded-md border border-brand-500 bg-brand-500 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:border-brand-600 hover:bg-brand-600"
          >
            New Upload
          </button>
          <button
            type="button"
            aria-label="Account menu"
            className="flex h-10 w-10 items-center justify-center rounded-full border border-slate-200 bg-white text-slate-500 shadow-sm transition hover:border-brand-300 hover:text-brand-600"
          >
            <svg
              width="20"
              height="20"
              viewBox="0 0 24 24"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
              aria-hidden="true"
              role="img"
            >
              <path
                d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4Zm0 2c-3.33 0-6 2-6 4.5V20h12v-1.5c0-2.5-2.67-4.5-6-4.5Z"
                fill="currentColor"
              />
            </svg>
          </button>
        </div>
      </header>
      <main className="flex flex-1 flex-col gap-6 overflow-y-auto bg-slate-50 p-6">
        <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <header className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
            <div>
              <h2 className="text-lg font-semibold text-slate-800">Filters</h2>
              <p className="text-sm text-slate-500">Refine the job timeline and list using document metadata.</p>
            </div>
            <div className="flex flex-wrap gap-3">
              <button
                type="button"
                onClick={handleResetFilters}
                className="rounded-md border border-slate-200 px-3 py-2 text-sm font-medium text-slate-600 transition hover:border-slate-300 hover:text-slate-800"
              >
                Reset
              </button>
            </div>
          </header>
          <div className="mt-4">
            <div className="grid gap-4 md:grid-cols-3 xl:grid-cols-6">
              <label className="flex flex-col gap-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
                Document name
                <input
                  type="text"
                  value={searchTerm}
                  onChange={(event) => setSearchTerm(event.target.value)}
                  placeholder="Search by name"
                  className="w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 shadow-sm transition focus:border-brand-400 focus:outline-none focus:ring focus:ring-brand-200"
                />
              </label>
              <label className="flex flex-col gap-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
                Status
                <select
                  value={statusFilter}
                  onChange={(event) => setStatusFilter(event.target.value as typeof statusFilter)}
                  className="w-full appearance-none rounded-md border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 shadow-sm transition focus:border-brand-400 focus:outline-none focus:ring focus:ring-brand-200"
                >
                  <option value="all">All statuses</option>
                  {Object.keys(STATUS_LABELS).map((status) => (
                    <option key={status} value={status}>
                      {STATUS_LABELS[status] ?? status}
                    </option>
                  ))}
                </select>
              </label>
              <label className="flex flex-col gap-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
                Min pages
                <input
                  type="number"
                  inputMode="numeric"
                  min={0}
                  value={minPages}
                  onChange={(event) => setMinPages(event.target.value)}
                  placeholder="0"
                  className="w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 shadow-sm transition focus:border-brand-400 focus:outline-none focus:ring focus:ring-brand-200"
                />
              </label>
              <label className="flex flex-col gap-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
                Max pages
                <input
                  type="number"
                  inputMode="numeric"
                  min={0}
                  value={maxPages}
                  onChange={(event) => setMaxPages(event.target.value)}
                  placeholder="Unlimited"
                  className="w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 shadow-sm transition focus:border-brand-400 focus:outline-none focus:ring focus:ring-brand-200"
                />
              </label>
              <label className="flex flex-col gap-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
                Sort by
                <select
                  value={sortOption}
                  onChange={(event) => setSortOption(event.target.value as SortOption)}
                  className="w-full appearance-none rounded-md border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 shadow-sm transition focus:border-brand-400 focus:outline-none focus:ring focus:ring-brand-200"
                >
                  {Object.entries(SORT_LABELS).map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </label>
              <div className="flex flex-col gap-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
                Matching jobs
                <div className="w-full rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-medium text-slate-700 shadow-sm">
                  {filteredJobs.length} of {jobs.length}
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="grid grid-cols-1 gap-6 xl:grid-cols-3">
          <article className="xl:col-span-2 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <header className="flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold text-slate-800">Processing timeline</h2>
                <p className="text-sm text-slate-500">Horizontal axis shows completion dates; vertical tracks throughput metrics.</p>
              </div>
              {historyMetricsQuery.isFetching ? <span className="text-xs text-slate-400">Refreshing…</span> : null}
            </header>
            <div className="mt-4 h-72 w-full">
              {timelineData.length === 0 ? (
                <div className="flex h-full items-center justify-center text-sm text-slate-500">
                  No timeline data yet — upload a document to populate the chart.
                </div>
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={timelineData} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
                    <defs>
                      {CHART_COLORS.map((color, index) => (
                        <linearGradient key={color} id={`gradient-${index}`} x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor={color} stopOpacity={0.4} />
                          <stop offset="95%" stopColor={color} stopOpacity={0} />
                        </linearGradient>
                      ))}
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                    <XAxis
                      dataKey="timestamp"
                      type="number"
                      scale="time"
                      domain={['dataMin', 'dataMax']}
                      stroke="#94a3b8"
                      tickLine={false}
                      axisLine={{ stroke: '#cbd5f5' }}
                      tickFormatter={formatTimelineTick}
                    />
                    <YAxis stroke="#94a3b8" tickLine={false} axisLine={{ stroke: '#cbd5f5' }} allowDecimals={false} />
                    <Tooltip
                      formatter={(value, name) => {
                        const labelMap: Record<string, string> = {
                          totalPages: 'Pages processed',
                          totalFields: 'Fields extracted',
                          totalTables: 'Tables detected',
                          processingMinutes: 'Processing minutes'
                        }
                        return [value as number, labelMap[name as string] ?? name]
                      }}
                      labelFormatter={(value) => formatTimelineTooltipLabel(value as number)}
                    />
                    <Legend />
                    <Area type="monotone" dataKey="totalPages" name="Pages processed" stroke={CHART_COLORS[0]} fill="url(#gradient-0)" strokeWidth={2} />
                    <Area type="monotone" dataKey="totalFields" name="Fields extracted" stroke={CHART_COLORS[1]} fill="url(#gradient-1)" strokeWidth={2} />
                    <Area type="monotone" dataKey="totalTables" name="Tables detected" stroke={CHART_COLORS[2]} fill="url(#gradient-2)" strokeWidth={2} />
                    <Area type="monotone" dataKey="processingMinutes" name="Processing minutes" stroke={CHART_COLORS[3]} fill="url(#gradient-3)" strokeWidth={2} />
                  </AreaChart>
                </ResponsiveContainer>
              )}
            </div>
          </article>

          <article className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <h2 className="text-lg font-semibold text-slate-800">Status mix</h2>
            <p className="text-sm text-slate-500">Track where jobs sit across the lifecycle.</p>
            <div className="mt-4 h-64">
              {statusBreakdown.length === 0 ? (
                <div className="flex h-full items-center justify-center text-sm text-slate-500">
                  No jobs to visualise yet.
                </div>
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Tooltip formatter={(value, name) => [`${value as number} jobs`, STATUS_LABELS[name as string] ?? name]} />
                    <Legend />
                    <Pie dataKey="count" data={statusBreakdown} innerRadius={50} outerRadius={80} paddingAngle={2}>
                      {statusBreakdown.map((entry, index) => (
                        <Cell key={entry.status} fill={CHART_COLORS[index % CHART_COLORS.length]} />
                      ))}
                    </Pie>
                  </PieChart>
                </ResponsiveContainer>
              )}
            </div>
          </article>
        </section>

        <section className="grid grid-cols-1 gap-6 xl:grid-cols-3">
          <article className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <h2 className="text-lg font-semibold text-slate-800">Confidence histogram</h2>
            <p className="text-sm text-slate-500">Distribution of field-level confidence scores across processed jobs.</p>
            <div className="mt-4 h-64">
              {confidenceHistogramData.every((entry) => entry.count === 0) ? (
                <div className="flex h-full items-center justify-center text-sm text-slate-500">
                  Confidence data will appear after processing documents.
                </div>
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={confidenceHistogramData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                    <XAxis dataKey="bucket" stroke="#94a3b8" tickLine={false} axisLine={{ stroke: '#cbd5f5' }} />
                    <YAxis allowDecimals={false} stroke="#94a3b8" tickLine={false} axisLine={{ stroke: '#cbd5f5' }} />
                    <Tooltip formatter={(value) => [`${value as number} fields`, 'Confidence bucket']} />
                    <Bar dataKey="count" name="Fields" fill={CHART_COLORS[1]} radius={[6, 6, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>
          </article>

          <article className="xl:col-span-2 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <header className="flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold text-slate-800">Low-confidence watch list</h2>
                <p className="text-sm text-slate-500">Fields with confidence &lt;= 0.40 that may require manual review.</p>
              </div>
              <div className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                {totalLowConfidenceFields} flagged
              </div>
            </header>
            <div className="mt-4 max-h-64 overflow-y-auto">
              {lowConfidenceFieldsQuery.isPending ? (
                <div className="py-6 text-sm text-slate-500">Loading low-confidence fields…</div>
              ) : lowConfidenceFieldsQuery.isError ? (
                <div className="py-6 text-sm text-rose-600">Unable to load low-confidence fields.</div>
              ) : (lowConfidenceFieldsQuery.data?.length ?? 0) === 0 ? (
                <div className="py-6 text-sm text-slate-500">No fields fall at or below the 0.40 threshold.</div>
              ) : (
                <table className="w-full table-fixed text-sm">
                  <thead>
                    <tr className="border-b border-slate-200 text-left text-xs uppercase tracking-wide text-slate-500">
                      <th className="w-2/5 py-2 pr-3">Document</th>
                      <th className="w-12 py-2 pr-3">Page</th>
                      <th className="w-1/5 py-2 pr-3">Field</th>
                      <th className="py-2 pr-3">Value</th>
                      <th className="w-16 py-2 pr-3 text-right">Conf.</th>
                    </tr>
                  </thead>
                  <tbody>
                    {lowConfidenceFieldsQuery.data?.map((field) => (
                      <tr
                        key={`${field.jobId}-${field.page}-${field.name}-${field.value}`}
                        className="cursor-pointer border-b border-slate-100 transition hover:bg-slate-50"
                        onClick={() => {
                          const jobSummary = jobs.find((job) => job.jobId === field.jobId)
                          if (jobSummary) {
                            handleOpenJob(jobSummary)
                          } else {
                            openJob(field.jobId)
                          }
                        }}
                      >
                        <td className="truncate py-2 pr-3" title={field.documentName}>
                          {field.documentName}
                        </td>
                        <td className="py-2 pr-3 text-slate-500">{field.page}</td>
                        <td className="truncate py-2 pr-3 text-slate-600" title={field.name}>
                          {field.name}
                        </td>
                        <td className="truncate py-2 pr-3 text-slate-500" title={field.value}>
                          {field.value}
                        </td>
                        <td className="py-2 pr-3 text-right">
                          <span className="rounded-full bg-rose-50 px-2 py-0.5 text-xs font-semibold text-rose-600">
                            {field.confidence.toFixed(2)}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </article>
        </section>

        <section className="rounded-xl border border-slate-200 bg-white shadow-sm">
          <header className="flex items-center justify-between border-b border-slate-200 px-5 py-4">
            <div>
              <h2 className="text-lg font-semibold text-slate-800">Job ledger</h2>
              <p className="text-sm text-slate-500">Click a row to reopen the job in the review workspace.</p>
            </div>
            {historyJobsQuery.isFetching ? <span className="text-xs text-slate-400">Refreshing…</span> : null}
          </header>
          <div className="divide-y divide-slate-100">
            {historyJobsQuery.isPending ? (
              <div className="px-5 py-6 text-sm text-slate-500">Loading job history…</div>
            ) : filteredJobs.length === 0 ? (
              <div className="px-5 py-6 text-sm text-slate-500">
                No jobs match the current filters. Adjust filters above to continue exploring results.
              </div>
            ) : (
              filteredJobs.map((job) => {
                const isDeleting = deletingJobId === job.jobId && deleteJobMutation.isPending
                return (
                  <div
                    key={job.jobId}
                    className="group flex flex-col gap-3 px-5 py-4 transition hover:bg-slate-50"
                  >
                    <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:gap-6">
                      <button
                        type="button"
                        onClick={() => handleOpenJob(job)}
                        className="flex flex-1 flex-col gap-2 text-left focus:outline-none"
                      >
                        <div className="flex flex-col gap-3 md:flex-row md:items-center md:gap-6">
                          <div className="flex items-center gap-4">
                            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-brand-50 text-sm font-semibold text-brand-600">
                              {job.totalPages}
                            </div>
                            <div className="min-w-0">
                              <p className="text-sm font-semibold text-slate-800 line-clamp-2 md:line-clamp-1">{job.documentName}</p>
                              {job.documentType ? (
                                <p className="mt-0.5 text-[0.65rem] font-semibold uppercase tracking-wide text-slate-400">
                                  {job.documentType}
                                </p>
                              ) : null}
                            </div>
                          </div>
                          <div className="flex flex-wrap items-center gap-3 text-xs text-slate-500 md:flex-1">
                            <span>
                              Fields {job.totalFields} · Tables {job.totalTables} · Processing {formatDuration(job.totalProcessingMs)}
                            </span>
                            <span>Finished {formatDateTime(job.finishedAt)}</span>
                            <span>Updated {formatDateTime(job.lastModified)}</span>
                          </div>
                        </div>
                      </button>
                      <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${STATUS_BADGE_CLASS[job.status] ?? 'bg-slate-100 text-slate-600'}`}>
                        {STATUS_LABELS[job.status] ?? job.status}
                      </span>
                      <button
                        type="button"
                        onClick={() => handleDeleteJob(job.jobId)}
                        className="self-start rounded-md border border-rose-200 px-3 py-2 text-xs font-medium text-rose-600 transition hover:border-rose-300 hover:text-rose-700 disabled:cursor-wait disabled:border-rose-100 disabled:text-rose-300"
                        disabled={isDeleting}
                      >
                        {isDeleting ? 'Deleting…' : 'Delete'}
                      </button>
                    </div>
                  </div>
                )
              })
            )}
          </div>
        </section>
      </main>
    </AppShell>
  )
}

export default DashboardPage
