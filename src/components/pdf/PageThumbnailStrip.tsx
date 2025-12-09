import clsx from 'clsx'
import type { PageExtraction } from '../../types/extraction'
import { buildMarkdownPreview } from '../../utils/markdown'

type PageThumbnailStripProps = {
  pages?: PageExtraction[]
  currentPage: number
  onSelectPage: (pageNumber: number) => void
  isLoading: boolean
}

const PageThumbnailStrip = ({
  pages,
  currentPage,
  onSelectPage,
  isLoading
}: PageThumbnailStripProps) => {
  if (isLoading) {
    return (
      <div className="flex gap-2 overflow-x-auto px-3 pb-3">
        {Array.from({ length: 4 }).map((_, index) => (
          <div
            key={index}
            className="h-16 w-12 animate-pulse rounded-md bg-slate-200"
          />
        ))}
      </div>
    )
  }

  if (!pages || pages.length === 0) {
    return null
  }

  return (
    <div className="flex gap-2 overflow-x-auto px-3 pb-3" aria-label="Page thumbnails">
      {pages.map((page) => {
        const previewSnippet = page.markdownText ? buildMarkdownPreview(page.markdownText, 40) : null
        return (
          <button
            key={page.pageNumber}
            type="button"
            onClick={() => onSelectPage(page.pageNumber)}
            className={clsx(
              'relative flex h-16 w-12 flex-col items-center justify-center overflow-hidden rounded-md border text-xs font-medium transition',
              currentPage === page.pageNumber
                ? 'border-brand-500 bg-brand-50 text-brand-600'
                : 'border-slate-200 bg-white text-slate-500 hover:border-brand-300'
            )}
          >
            {page.documentTypeHint ? (
              <span className="absolute left-1 top-1 z-10 rounded-full bg-slate-900/70 px-1.5 py-px text-[0.5rem] font-semibold uppercase tracking-wide text-white">
                {page.documentTypeHint.length > 10 ? `${page.documentTypeHint.slice(0, 10)}…` : page.documentTypeHint}
              </span>
            ) : null}
            {page.imageUrl ? (
              <>
                <img
                  src={page.imageUrl}
                  alt={`Page ${page.pageNumber}`}
                  className="absolute inset-0 h-full w-full object-cover"
                />
                <div className="absolute inset-0 bg-slate-900/25" aria-hidden />
              </>
            ) : null}
            <span className="relative z-10 drop-shadow-sm">Page</span>
            <span className="relative z-10 text-base drop-shadow-sm">{page.pageNumber}</span>
            {!page.imageUrl && previewSnippet ? (
              <span className="relative z-10 mt-1 w-full truncate px-1 text-[0.55rem] text-slate-500">
                {previewSnippet}
              </span>
            ) : null}
          </button>
        )
      })}
    </div>
  )
}

export default PageThumbnailStrip
