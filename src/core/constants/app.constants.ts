/**
 * Application-wide constants
 * Extracted from scattered definitions across components
 */

export const CHART_COLORS = ['#6366F1', '#0EA5E9', '#22C55E', '#F97316', '#EC4899'] as const

export const STATUS_LABELS: Record<string, string> = {
  queued: 'Queued',
  running: 'In Progress',
  completed: 'Completed',
  partial: 'Partial',
  error: 'Error'
}

export const STATUS_BADGE_CLASS: Record<string, string> = {
  queued: 'bg-amber-100 text-amber-700 border border-amber-200',
  running: 'bg-sky-100 text-sky-700 border border-sky-200',
  completed: 'bg-emerald-100 text-emerald-700 border border-emerald-200',
  partial: 'bg-indigo-100 text-indigo-700 border border-indigo-200',
  error: 'bg-rose-100 text-rose-700 border border-rose-200'
}

export const CONFIDENCE_BUCKET_LABELS = ['0-0.2', '0.2-0.4', '0.4-0.6', '0.6-0.8', '0.8-<1.0', '1.0'] as const
