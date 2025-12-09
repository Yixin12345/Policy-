import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  fetchDashboardMetrics,
  fetchJobHistory,
  fetchJobHistoryDetail,
  fetchLowConfidenceFields,
  savePageEdits
} from '../services/apiClient'
import type {
  DashboardMetrics,
  JobHistoryDetail,
  JobHistorySummary,
  LowConfidenceField,
  SaveEditsRequest,
  SaveEditsResponse
} from '../types/extraction'

const historyJobsKey = ['history', 'jobs'] as const
const historyMetricsKey = ['history', 'metrics'] as const
const historyDetailKey = (jobId: string | null) => ['history', 'jobs', jobId] as const
const lowConfidenceKey = (limit: number, jobId?: string) => ['history', 'low-confidence', { limit, jobId }] as const

export function useHistoryJobs() {
  return useQuery<JobHistorySummary[], Error>({
    queryKey: historyJobsKey,
    queryFn: () => fetchJobHistory(),
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  })
}

export function useHistoryMetrics() {
  return useQuery<DashboardMetrics, Error>({
    queryKey: historyMetricsKey,
    queryFn: () => fetchDashboardMetrics(),
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  })
}

export function useHistoryJobDetail(jobId: string | null) {
  return useQuery<JobHistoryDetail, Error>({
    queryKey: historyDetailKey(jobId),
    queryFn: () => fetchJobHistoryDetail(jobId as string),
    enabled: Boolean(jobId),
    staleTime: 60_000,
    refetchOnWindowFocus: false,
    refetchInterval: (query) => {
      if (!jobId) {
        return false
      }
      const detail = query.state.data
      if (!detail) {
        return 4000
      }
      const terminalStates: JobHistoryDetail['status']['state'][] = ['completed', 'partial', 'error']
      const isTerminal = terminalStates.includes(detail.status.state)
      const hasCanonical = Boolean(detail.canonical)
      return isTerminal && hasCanonical ? false : 4000
    },
  })
}

export function useLowConfidenceFields(limit = 50, jobId?: string) {
  return useQuery<LowConfidenceField[], Error>({
    queryKey: lowConfidenceKey(limit, jobId),
    queryFn: () => fetchLowConfidenceFields(limit, jobId),
    staleTime: 30_000,
    refetchOnWindowFocus: false,
  })
}

export function useSavePageEdits(jobId: string | null) {
  const queryClient = useQueryClient()

  return useMutation<SaveEditsResponse, Error, SaveEditsRequest>({
    mutationKey: ['history', 'jobs', jobId, 'save-edits'],
    mutationFn: (payload) => {
      if (!jobId) {
        throw new Error('Job ID is required to save edits')
      }
      return savePageEdits(jobId, payload)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: historyJobsKey })
      queryClient.invalidateQueries({ queryKey: historyMetricsKey })
      if (jobId) {
        queryClient.invalidateQueries({ queryKey: historyDetailKey(jobId) })
      }
      queryClient.invalidateQueries({
        predicate: (query) =>
          Array.isArray(query.queryKey) && query.queryKey[0] === 'history' && query.queryKey[1] === 'low-confidence',
      })
    },
  })
}
