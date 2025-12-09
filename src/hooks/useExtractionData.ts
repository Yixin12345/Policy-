import { useMutation, useQuery } from '@tanstack/react-query'
import {
  fetchAggregatedResults,
  fetchAllPages,
  fetchJobStatus,
  fetchCanonicalBundle,
  fetchPageResult,
  uploadDocument
} from '../services/apiClient'
import type {
  AggregatedResults,
  CanonicalBundleResponse,
  JobStatus,
  PageExtraction,
  UploadResponse
} from '../types/extraction'
import { useViewerStore } from '../state/viewerStore'

const jobStatusKey = (jobId: string | null) => ['job-status', jobId]
const pagesKey = (jobId: string | null) => ['pages', jobId]
const pageKey = (jobId: string | null, pageNumber: number) => [
  'page',
  jobId,
  pageNumber
]
const aggregatedKey = (jobId: string | null) => ['aggregated', jobId]
const canonicalKey = (jobId: string | null) => ['canonical', jobId]

export function useUploadJob() {
  const setJobId = useViewerStore((state) => state.setJobId)

  return useMutation<UploadResponse, Error, File>({
    mutationFn: uploadDocument,
    onSuccess: (response) => {
      setJobId(response.jobId)
    }
  })
}

export function useJobStatus(jobId: string | null) {
  return useQuery<JobStatus, Error>({
    queryKey: jobStatusKey(jobId),
    queryFn: () => fetchJobStatus(jobId as string),
    enabled: Boolean(jobId),
    refetchOnWindowFocus: false,
    refetchInterval: (query) => {
      if (!jobId) return false
      const data = query.state.data
      if (!data) return 2000
      return ['completed', 'partial', 'error'].includes(data.state) ? false : 2000
    }
  })
}

export function usePages(jobId: string | null) {
  return useQuery<PageExtraction[], Error>({
    queryKey: pagesKey(jobId),
    queryFn: () => fetchAllPages(jobId as string),
    enabled: Boolean(jobId),
    refetchOnWindowFocus: false,
    refetchInterval: (query) => {
      if (!jobId) return false
      const pages = query.state.data
      if (!pages || pages.length === 0) {
        return 3000
      }
      const allDone = pages.every((page) => page.status === 'completed' || page.status === 'error')
      return allDone ? false : 3000
    }
  })
}

export function usePageData(jobId: string | null, pageNumber: number) {
  return useQuery<PageExtraction, Error>({
    queryKey: pageKey(jobId, pageNumber),
    queryFn: () => fetchPageResult(jobId as string, pageNumber),
    enabled: Boolean(jobId && pageNumber > 0),
    staleTime: 60_000,
    refetchOnWindowFocus: false,
    refetchInterval: (query) => {
      if (!jobId) return false
      const page = query.state.data
      if (!page) return 2000
      return page.status === 'completed' || page.status === 'error' ? false : 2000
    }
  })
}

export function useAggregated(jobId: string | null, enabled: boolean) {
  return useQuery<AggregatedResults, Error>({
    queryKey: aggregatedKey(jobId),
    queryFn: () => fetchAggregatedResults(jobId as string),
    enabled,
    staleTime: 60_000,
    refetchOnWindowFocus: false,
    refetchInterval: (query) => {
      if (!enabled) return false
      const data = query.state.data
      if (!data) return 4000
      return data.fields.length > 0 ? false : 4000
    }
  })
}

export function useCanonicalBundle(jobId: string | null, enabled: boolean) {
  return useQuery<CanonicalBundleResponse, Error>({
    queryKey: canonicalKey(jobId),
    queryFn: () => fetchCanonicalBundle(jobId as string),
    enabled,
    staleTime: 60_000,
    refetchOnWindowFocus: false,
    retry: false,
  })
}
