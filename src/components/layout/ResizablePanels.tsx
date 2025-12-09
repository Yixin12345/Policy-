import type { ReactNode } from 'react'
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'

type ResizablePanelsProps = {
  left: ReactNode
  right: ReactNode
  minLeftPercent?: number
  minRightPercent?: number
}

const clamp = (value: number, min: number, max: number) => Math.min(Math.max(value, min), max)

const ResizablePanels = ({
  left,
  right,
  minLeftPercent = 25,
  minRightPercent = 25
}: ResizablePanelsProps) => {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const [leftPercent, setLeftPercent] = useState<number>(50)
  const [isDragging, setIsDragging] = useState(false)
  const [isVertical, setIsVertical] = useState(true)

  useLayoutEffect(() => {
    const container = containerRef.current
    if (!container || typeof ResizeObserver === 'undefined') return

    const observer = new ResizeObserver((entries) => {
      const entry = entries[0]
      setIsVertical(entry.contentRect.width < 768)
    })

    observer.observe(container)
    return () => observer.disconnect()
  }, [])

  useEffect(() => {
    if (!isDragging) return

    const previousCursor = document.body.style.cursor
    const previousUserSelect = document.body.style.userSelect
    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'

    return () => {
      document.body.style.cursor = previousCursor
      document.body.style.userSelect = previousUserSelect
    }
  }, [isDragging])

  const handlePointerMove = useCallback(
    (event: PointerEvent) => {
      if (!containerRef.current) return
      const rect = containerRef.current.getBoundingClientRect()
      const offsetX = event.clientX - rect.left
      const rawPercent = (offsetX / rect.width) * 100
      const maxLeft = 100 - minRightPercent
      const clamped = clamp(rawPercent, minLeftPercent, maxLeft)
      setLeftPercent(clamped)
    },
    [minLeftPercent, minRightPercent]
  )

  const stopDragging = useCallback(() => {
    setIsDragging(false)
    window.removeEventListener('pointermove', handlePointerMove)
    window.removeEventListener('pointerup', stopDragging)
  }, [handlePointerMove])

  const startDragging = useCallback(
    (event: React.PointerEvent<HTMLDivElement>) => {
      if (isVertical) return
      event.preventDefault()
      setIsDragging(true)
      window.addEventListener('pointermove', handlePointerMove)
      window.addEventListener('pointerup', stopDragging)
    },
    [handlePointerMove, isVertical, stopDragging]
  )

  useEffect(() => {
    return () => {
      window.removeEventListener('pointermove', handlePointerMove)
      window.removeEventListener('pointerup', stopDragging)
    }
  }, [handlePointerMove, stopDragging])

  const adjustBy = useCallback(
    (delta: number) => {
      setLeftPercent((current) => {
        const maxLeft = 100 - minRightPercent
        const next = clamp(current + delta, minLeftPercent, maxLeft)
        return next
      })
    },
    [minLeftPercent, minRightPercent]
  )

  const handleKeyDown = useCallback(
    (event: React.KeyboardEvent<HTMLDivElement>) => {
      if (isVertical) return
      if (event.key === 'ArrowLeft') {
        event.preventDefault()
        adjustBy(-2)
      }
      if (event.key === 'ArrowRight') {
        event.preventDefault()
        adjustBy(2)
      }
    },
    [adjustBy, isVertical]
  )

  const leftPaneStyle = useMemo(() => {
    if (isVertical) {
      return { width: '100%' }
    }

    return {
      flexBasis: `${leftPercent}%`,
      maxWidth: `${leftPercent}%`,
      flexGrow: 0,
      flexShrink: 0
    }
  }, [isVertical, leftPercent])

  const rightPaneStyle = useMemo(() => {
    if (isVertical) {
      return { width: '100%' }
    }

    const rightPercent = 100 - leftPercent
    return {
      flexBasis: `${rightPercent}%`,
      maxWidth: `${rightPercent}%`,
      flexGrow: 0,
      flexShrink: 0
    }
  }, [isVertical, leftPercent])

  return (
    <div
      ref={containerRef}
      className="flex h-full w-full flex-col gap-4 xl:flex-row xl:items-stretch xl:gap-0"
    >
      <div className="flex h-full w-full" style={leftPaneStyle}>
        {left}
      </div>
      {!isVertical && (
        <div
          role="separator"
          aria-orientation="vertical"
          aria-valuemin={minLeftPercent}
          aria-valuemax={100 - minRightPercent}
          aria-valuenow={Math.round(leftPercent)}
          tabIndex={0}
          onPointerDown={startDragging}
          onKeyDown={handleKeyDown}
          className="group relative flex w-2 cursor-col-resize items-center justify-center px-0"
        >
          <div className="pointer-events-none h-full w-px bg-slate-200 group-hover:bg-brand-400" />
          <span className="pointer-events-none absolute -top-5 text-xs font-semibold text-slate-400 opacity-0 transition group-hover:opacity-100">
            ↔
          </span>
        </div>
      )}
      <div className="flex h-full w-full" style={rightPaneStyle}>
        {right}
      </div>
    </div>
  )
}

export default ResizablePanels
