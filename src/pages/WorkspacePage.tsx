import { useCallback, useEffect, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useNavigate, useParams } from 'react-router-dom'
import AppShell from '../components/layout/AppShell'
import ResizablePanels from '../components/layout/ResizablePanels'
import HeaderBar from '../components/header/HeaderBar'
import PdfViewer from '../components/pdf/PdfViewer'
import ResultsPanel from '../components/results/ResultsPanel'
import {
  useCanonicalBundle,
  useJobStatus,
  usePageData,
  usePages,
  useUploadJob
} from '../hooks/useExtractionData'
import type { CanonicalSelectPayload, HighlightRegion, PageClassification } from '../types/extraction'
import { useViewerStore } from '../state/viewerStore'
import { fetchJobHistoryDetail } from '../services/apiClient'

const WorkspacePage = () => {
  const navigate = useNavigate()
  const { jobId: routeJobId } = useParams<{ jobId?: string }>()
  const queryClient = useQueryClient()

  const jobId = useViewerStore((state) => state.jobId)
  const currentPage = useViewerStore((state) => state.currentPage)
  const totalPages = useViewerStore((state) => state.totalPages)
  const setJobId = useViewerStore((state) => state.setJobId)
  const setCurrentPage = useViewerStore((state) => state.setCurrentPage)
  const setTotalPages = useViewerStore((state) => state.setTotalPages)

  const uploadMutation = useUploadJob()
  const statusQuery = useJobStatus(jobId)
  const pagesQuery = usePages(jobId)
  const pageQuery = usePageData(jobId, currentPage)
  const canonicalEnabled = Boolean(
    jobId && statusQuery.data && ['completed', 'partial', 'error'].includes(statusQuery.data.state)
  )
  const canonicalQuery = useCanonicalBundle(jobId, canonicalEnabled)
  const canonicalPayload = canonicalQuery.data
  const canonicalBundle = canonicalPayload?.canonical ?? null
  const canonicalDocumentTypes = canonicalPayload?.documentTypes ?? canonicalBundle?.documentTypes ?? statusQuery.data?.documentTypes
  const canonicalDocumentCategories = canonicalPayload?.documentCategories ?? canonicalBundle?.documentCategories
  const canonicalDocumentType = canonicalDocumentTypes && canonicalDocumentTypes.length > 0
    ? canonicalDocumentTypes[0]
    : canonicalDocumentCategories && canonicalDocumentCategories.length > 0
      ? canonicalDocumentCategories[0]
      : statusQuery.data?.documentType ?? null
  const pageClassifications: PageClassification[] | undefined = canonicalPayload?.pageClassifications
  const [isExporting, setIsExporting] = useState(false)
  const [canonicalSelection, setCanonicalSelection] = useState<CanonicalSelectPayload | null>(null)
  const [highlights, setHighlights] = useState<HighlightRegion[]>([])

  const previousRouteJobId = useRef<string | undefined>(undefined)
  const previousJobId = useRef<string | null>(null)

  useEffect(() => {
    if (routeJobId === previousRouteJobId.current) {
      return
    }
    previousRouteJobId.current = routeJobId
    if (routeJobId) {
      setJobId(routeJobId)
      queryClient.invalidateQueries({ queryKey: ['job-status', routeJobId], exact: true })
      queryClient.invalidateQueries({ queryKey: ['pages', routeJobId], exact: true })
      queryClient.invalidateQueries({
        predicate: (query) => {
          const key = query.queryKey
          return Array.isArray(key) && key[0] === 'page' && key[1] === routeJobId
        }
      })
      queryClient.invalidateQueries({ queryKey: ['aggregated', routeJobId], exact: true })
      queryClient.invalidateQueries({ queryKey: ['history', 'jobs', routeJobId], exact: true })
    } else {
      setJobId(null)
    }
  }, [queryClient, routeJobId, setJobId])

  useEffect(() => {
    if (jobId && routeJobId !== jobId) {
      navigate(`/workspace/${jobId}`, { replace: !!routeJobId })
    } else if (!jobId && routeJobId && previousJobId.current !== null) {
      navigate('/workspace', { replace: true })
    }

    previousJobId.current = jobId ?? null
  }, [jobId, routeJobId, navigate])

  useEffect(() => {
    if (statusQuery.data) {
      setTotalPages(statusQuery.data.totalPages)
    }
  }, [setTotalPages, statusQuery.data])

  useEffect(() => {
    if (totalPages > 0 && currentPage > totalPages) {
      setCurrentPage(totalPages)
    }
  }, [currentPage, setCurrentPage, totalPages])

  const handleFileSelected = (file: File) => {
    uploadMutation.mutate(file)
  }

  const handleNavigateHistory = () => {
    // Mark history data stale so the dashboard refetches in-progress jobs immediately
    queryClient.invalidateQueries({
      predicate: (query) => Array.isArray(query.queryKey) && query.queryKey[0] === 'history'
    })
    navigate('/')
  }

  const handleExportJson = async () => {
    if (!jobId) {
      window.alert('Select a job before exporting results.')
      return
    }
    setIsExporting(true)
    try {
      const detail = await fetchJobHistoryDetail(jobId)
      const fileNameBase = detail.documentName?.trim() || `job-${jobId}`
      const safeFileName = fileNameBase.replace(/[^\w\-. ]+/g, '_')
      const exportPageClassifications = detail.pageClassifications
        ?? (Array.isArray(detail.metadata?.pageClassifications)
          ? detail.metadata.pageClassifications
          : undefined)
      const exportPayload = {
        jobId: detail.jobId,
        documentName: detail.documentName,
        summary: detail.summary,
        status: detail.status,
        pages: detail.pages,
        aggregated: detail.aggregated,
        metadata: detail.metadata,
        documentType: detail.documentType,
        canonical: detail.canonical,
        mappingTrace: detail.mappingTrace,
        pageClassifications: exportPageClassifications,
      }
      const json = JSON.stringify(exportPayload, null, 2)
      const blob = new Blob([json], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `${safeFileName || jobId}.json`
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      URL.revokeObjectURL(url)
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to export job results.'
      window.alert(message)
    } finally {
      setIsExporting(false)
    }
  }

  const handleCanonicalSelect = useCallback((selection: CanonicalSelectPayload | null) => {
    setCanonicalSelection(selection)
    if (!selection?.sources || selection.sources.length === 0) {
      return
    }

    let targetPage = selection.sources.find((source) => typeof source.page === 'number')?.page

    if (!targetPage && pagesQuery.data) {
      for (const source of selection.sources) {
        if (source.fieldId) {
          const matchedPage = pagesQuery.data.find((page) => page.fields.some((field) => field.id === source.fieldId))
          if (matchedPage) {
            targetPage = matchedPage.pageNumber
            break
          }
        }
        if (source.tableId) {
          const matchedPage = pagesQuery.data.find((page) => page.tables.some((table) => table.id === source.tableId))
          if (matchedPage) {
            targetPage = matchedPage.pageNumber
            break
          }
        }
      }
    }

    if (targetPage && targetPage !== currentPage) {
      setCurrentPage(targetPage)
    }
  }, [currentPage, pagesQuery.data, setCurrentPage])

  useEffect(() => {
    if (!canonicalSelection || !pagesQuery.data) {
      setHighlights([])
      return
    }
    const pageData = pagesQuery.data.find((item) => item.pageNumber === currentPage)
    if (!pageData) {
      setHighlights([])
      return
    }

    const nextHighlights: HighlightRegion[] = []
    const section = canonicalSelection.section ?? 'unknown'

    const normalizeColumn = (value: string) => value.replace(/[^a-z0-9]+/g, '').toLowerCase()

    const pushHighlight = (id: string, bboxData: { x: number; y: number; width: number; height: number } | undefined) => {
      if (!bboxData) {
        return
      }
      nextHighlights.push({
        id,
        page: pageData.pageNumber,
        bbox: bboxData,
        section,
        label: canonicalSelection.label,
      })
    }

    canonicalSelection.sources?.forEach((source, sourceIndex) => {
      const sourcePage = source.page ?? pageData.pageNumber
      if (sourcePage !== pageData.pageNumber) {
        return
      }

      if (source.fieldId) {
        const field = pageData.fields.find((item) => item.id === source.fieldId)
        if (field?.bbox) {
          pushHighlight(`field-${field.id}-${sourceIndex}`, field.bbox)
        }
        return
      }

      if (source.tableId) {
        const table = pageData.tables.find((item) => item.id === source.tableId)
        if (!table) {
          return
        }

        if (source.column) {
          const normalizedColumn = normalizeColumn(source.column)
          const columnIndex = table.columns.findIndex((column) => {
            const key = column.key ? normalizeColumn(column.key) : undefined
            const header = column.header ? normalizeColumn(column.header) : undefined
            return key === normalizedColumn || header === normalizedColumn
          })

          if (columnIndex >= 0) {
            let hasCellBbox = false
            table.rows.forEach((row, rowIndex) => {
              const cell = row[columnIndex]
              if (cell?.bbox) {
                hasCellBbox = true
                pushHighlight(`table-${table.id}-${columnIndex}-${rowIndex}`, cell.bbox)
              }
            })
            if (!hasCellBbox && table.bbox) {
              pushHighlight(`table-${table.id}-column-${columnIndex}`, table.bbox)
            }
          } else if (table.bbox) {
            pushHighlight(`table-${table.id}-full`, table.bbox)
          }
        } else if (table.bbox) {
          pushHighlight(`table-${table.id}`, table.bbox)
        }
      }
    })

    setHighlights(nextHighlights)
  }, [canonicalSelection, currentPage, pagesQuery.data])

  const isPdfLoading = statusQuery.isPending || pageQuery.isPending

  return (
    <AppShell>
      <HeaderBar
        onFileSelected={handleFileSelected}
        isUploading={uploadMutation.isPending}
        status={statusQuery.data}
        onGoToHistory={handleNavigateHistory}
        onExportJson={handleExportJson}
        isExporting={isExporting}
      />
      <main className="flex flex-1 flex-col overflow-hidden p-4">
        <ResizablePanels
          left={
            <PdfViewer
              page={pageQuery.data}
              pages={pagesQuery.data}
              currentPage={currentPage}
              totalPages={totalPages}
              onGoToPage={setCurrentPage}
              isLoading={isPdfLoading}
              highlights={highlights}
            />
          }
          right={
            <ResultsPanel
              pageFields={pageQuery.data?.fields}
              tables={pageQuery.data?.tables}
              page={pageQuery.data}
              isLoading={pageQuery.isPending}
              canonical={canonicalBundle}
              canonicalDocumentType={canonicalDocumentType}
              canonicalDocumentTypes={canonicalDocumentTypes}
              canonicalDocumentCategories={canonicalDocumentCategories}
              isCanonicalLoading={canonicalQuery.isPending || canonicalQuery.isFetching}
              pageClassifications={pageClassifications}
              onCanonicalSelect={handleCanonicalSelect}
            />
          }
        />
      </main>
    </AppShell>
  )
}

export default WorkspacePage
