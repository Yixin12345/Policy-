import clsx from 'clsx'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import PageThumbnailStrip from './PageThumbnailStrip'
import type { HighlightRegion, PageExtraction } from '../../types/extraction'
import { sanitizeMarkdownContent } from '../../utils/markdown'

type PdfViewerProps = {
  page?: PageExtraction
  pages?: PageExtraction[]
  currentPage: number
  totalPages: number
  onGoToPage: (pageNumber: number) => void
  isLoading: boolean
  highlights?: HighlightRegion[]
}

const PdfViewer = ({
  page,
  pages,
  currentPage,
  totalPages,
  onGoToPage,
  isLoading,
  highlights = [],
}: PdfViewerProps) => {
  const containerRef = useRef<HTMLDivElement>(null)
  const imageRef = useRef<HTMLImageElement>(null)
  const [naturalSize, setNaturalSize] = useState<{ width: number; height: number }>({ width: 8.5, height: 11 })
  const [imageReady, setImageReady] = useState(false)
  useEffect(() => {
    if (!page?.imageUrl) {
      setImageReady(false)
      return
    }
    setImageReady(false)
  }, [page?.imageUrl])

  const isImagePage = Boolean(page?.imageUrl)
  const isMarkdownPage = Boolean(page?.markdownText)
  const sanitizedMarkdown = useMemo(() => sanitizeMarkdownContent(page?.markdownText ?? ''), [page?.markdownText])
  const previewTitle = isMarkdownPage ? 'Markdown Preview' : 'Document Preview'

  const documentTypePresentation = useMemo(() => {
    if (!page?.documentTypeHint) {
      return null
    }

    const hint = page.documentTypeHint.toLowerCase()
    const palette: Record<string, { label: string; colorClass: string }> = {
      policy_conversion: { label: 'Policy_Conversion', colorClass: 'text-indigo-600' },
    }

    const defaultLabel = page.documentTypeHint
      .split('_')
      .map((segment) => (segment.length <= 3 ? segment.toUpperCase() : segment.charAt(0).toUpperCase() + segment.slice(1)))
      .join('_')

    const mapping = palette[hint] ?? { label: defaultLabel, colorClass: 'text-violet-600' }
    const confidencePercent = page.documentTypeConfidence !== undefined
      ? Math.round((page.documentTypeConfidence ?? 0) * 100)
      : undefined

    return {
      ...mapping,
      confidencePercent,
    }
  }, [page?.documentTypeConfidence, page?.documentTypeHint])

  const handleImageLoad = useCallback((event: React.SyntheticEvent<HTMLImageElement>) => {
    const img = event.currentTarget
    const width = img.naturalWidth || naturalSize.width
    const height = img.naturalHeight || naturalSize.height
    setNaturalSize({ width, height })
    setImageReady(true)
  }, [naturalSize.height, naturalSize.width])

  const aspectRatio = naturalSize.width > 0 && naturalSize.height > 0
    ? naturalSize.width / naturalSize.height
    : 8.5 / 11

  const highlightPalette = useMemo<Record<HighlightRegion['section'], { border: string; background: string; labelBg: string; labelText: string }>>(() => ({
    policy_conversion: {
      border: 'border-indigo-500/90',
      background: 'bg-indigo-400/15',
      labelBg: 'bg-indigo-500',
      labelText: 'text-white',
    },
    unknown: {
      border: 'border-violet-500/80',
      background: 'bg-violet-400/15',
      labelBg: 'bg-violet-500',
      labelText: 'text-white',
    },
  }), [])

  type Palette = (typeof highlightPalette)[HighlightRegion['section']]
  type ProcessedHighlight = {
    region: HighlightRegion
    palette: Palette
    style: { left: string; top: string; width: string; height: string }
  }

  const processedHighlights = useMemo<ProcessedHighlight[]>(() => {
    if (!page || !page.imageUrl || highlights.length === 0) {
      return []
    }
    const width = naturalSize.width || 1
    const height = naturalSize.height || 1

    return highlights
      .filter((highlight) => highlight.page === page.pageNumber && highlight.bbox)
      .map((highlight) => {
        const palette = highlightPalette[highlight.section] ?? highlightPalette.unknown
        const bbox = highlight.bbox
        if (!bbox) {
          return null
        }

        const isNormalized =
          bbox.x >= 0 && bbox.x <= 1 &&
          bbox.y >= 0 && bbox.y <= 1 &&
          bbox.width >= 0 && bbox.width <= 1 &&
          bbox.height >= 0 && bbox.height <= 1

        const absX = isNormalized ? bbox.x * width : bbox.x
        const absY = isNormalized ? bbox.y * height : bbox.y
        const absWidth = isNormalized ? bbox.width * width : bbox.width
        const absHeight = isNormalized ? bbox.height * height : bbox.height

        if (absWidth <= 0 || absHeight <= 0) {
          return null
        }

        const left = Math.max(0, Math.min((absX / width) * 100, 100))
        const top = Math.max(0, Math.min((absY / height) * 100, 100))
        const right = Math.max(0, Math.min(((absX + absWidth) / width) * 100, 100))
        const bottom = Math.max(0, Math.min(((absY + absHeight) / height) * 100, 100))
        const style = {
          left: `${left}%`,
          top: `${top}%`,
          width: `${Math.max(0, right - left)}%`,
          height: `${Math.max(0, bottom - top)}%`,
        }

        return {
          region: highlight,
          palette,
          style: style as ProcessedHighlight['style'],
        } as ProcessedHighlight
      })
      .filter((item): item is ProcessedHighlight => Boolean(item))
  }, [highlightPalette, highlights, naturalSize.height, naturalSize.width, page])

  const handlePrev = () => {
    if (currentPage > 1) onGoToPage(currentPage - 1)
  }

  const handleNext = () => {
    if (page && currentPage < totalPages) onGoToPage(currentPage + 1)
  }

  return (
    <section className="flex flex-1 flex-col overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
      <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
        <div>
          <h2 className="text-sm font-semibold text-slate-700">{previewTitle}</h2>
          <p className="text-xs text-slate-500">
            Page {page ? page.pageNumber : currentPage} of {totalPages || '—'}
          </p>
          {documentTypePresentation ? (
            <p className="text-[0.7rem] tracking-wide text-slate-500">
              <span className="font-medium text-slate-600">Page Category:</span>{' '}
              <span className={clsx('font-semibold', documentTypePresentation.colorClass)}>
                {documentTypePresentation.label}
              </span>
              {documentTypePresentation.confidencePercent !== undefined ? (
                <span className="text-slate-400"> ({documentTypePresentation.confidencePercent}%)</span>
              ) : null}
            </p>
          ) : null}
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={handlePrev}
            disabled={currentPage <= 1 || isLoading}
            className={clsx(
              'rounded-md border px-2 py-1 text-sm font-medium transition',
              currentPage <= 1 || isLoading
                ? 'cursor-not-allowed border-slate-200 text-slate-300'
                : 'border-slate-200 text-slate-600 hover:border-brand-300 hover:text-brand-600'
            )}
          >
            Prev
          </button>
          <button
            type="button"
            onClick={handleNext}
            disabled={!page || currentPage >= totalPages || isLoading}
            className={clsx(
              'rounded-md border px-2 py-1 text-sm font-medium transition',
              !page || currentPage >= totalPages || isLoading
                ? 'cursor-not-allowed border-slate-200 text-slate-300'
                : 'border-slate-200 text-slate-600 hover:border-brand-300 hover:text-brand-600'
            )}
          >
            Next
          </button>
        </div>
      </div>
      <div className="flex-1 overflow-auto bg-slate-100 p-6">
        {isLoading ? (
          <div className="flex h-full items-center justify-center">
            <div className="h-24 w-16 animate-pulse rounded-lg bg-slate-300" />
          </div>
        ) : page ? (
          <div className="mx-auto flex h-full max-w-3xl items-center justify-center">
            <div
              ref={containerRef}
              className="relative flex w-full overflow-hidden rounded-lg border border-slate-300 bg-white shadow-inner"
              style={isImagePage ? { aspectRatio } : undefined}
            >
              {isImagePage ? (
                <>
                  <img
                    ref={imageRef}
                    src={page.imageUrl}
                    alt={`Page ${page.pageNumber}`}
                    className="h-full w-full bg-slate-100 object-contain"
                    onLoad={handleImageLoad}
                  />
                  {processedHighlights.length > 0 ? (
                    <div className="pointer-events-none absolute inset-0 z-10">
                      {processedHighlights.map(({ region, palette, style }) => (
                        <div
                          key={region.id}
                          className={clsx(
                            'pointer-events-none absolute rounded border-2 shadow-sm transition-opacity',
                            palette.border,
                            palette.background,
                            { 'opacity-0': Boolean(page?.imageUrl) && !imageReady }
                          )}
                          style={style}
                        >
                          <span
                            className={clsx(
                              'absolute left-0 top-0 translate-y-[-100%] rounded-t px-2 py-0.5 text-[0.625rem] font-semibold uppercase tracking-wide shadow',
                              palette.labelBg,
                              palette.labelText
                            )}
                          >
                            {region.label}
                          </span>
                        </div>
                      ))}
                    </div>
                  ) : null}
                </>
              ) : isMarkdownPage ? (
                <div className="flex h-full w-full flex-col">
                  <div className="flex-1 overflow-auto p-6">
                    {sanitizedMarkdown ? (
                      <pre className="whitespace-pre-wrap break-words text-sm leading-relaxed text-slate-800">
                        {sanitizedMarkdown}
                      </pre>
                    ) : (
                      <div className="flex h-full items-center justify-center text-sm text-slate-400">
                        Markdown content unavailable for this page.
                      </div>
                    )}
                  </div>
                </div>
              ) : (
                <div className="flex h-full w-full flex-col items-center justify-center gap-2 text-slate-400">
                  <span className="text-lg font-semibold">Page {page.pageNumber}</span>
                  <span className="text-xs">Preview not available</span>
                </div>
              )}
            </div>
          </div>
        ) : (
          <div className="flex h-full items-center justify-center text-sm text-slate-500">
            Upload a document to preview pages here.
          </div>
        )}
      </div>
      <PageThumbnailStrip
        pages={pages}
        currentPage={currentPage}
        onSelectPage={onGoToPage}
        isLoading={isLoading}
      />
    </section>
  )
}

export default PdfViewer
