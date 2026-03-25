import { ChevronLeft, ChevronRight, ImageIcon, X } from 'lucide-react'
import { useEffect, useId, useMemo, useRef, useState } from 'react'

import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils/format'
import { frameImageUrl } from '@/lib/utils/frames'

type ScreenshotModalProps = {
  open: boolean
  onClose: () => void
  lessonId: string
  frameIds: string[]
  initialIndex?: number
}

type ImageStatus = 'loading' | 'loaded' | 'error'

function clampIndex(index: number, frameIds: string[]): number {
  if (frameIds.length === 0) return 0
  return Math.min(Math.max(index, 0), frameIds.length - 1)
}

export function ScreenshotModal({
  open,
  onClose,
  lessonId,
  frameIds,
  initialIndex = 0,
}: ScreenshotModalProps) {
  const titleId = useId()
  const dialogRef = useRef<HTMLDivElement>(null)
  const closeButtonRef = useRef<HTMLButtonElement>(null)
  const [currentIndex, setCurrentIndex] = useState(() => clampIndex(initialIndex, frameIds))
  const [imageStatus, setImageStatus] = useState<ImageStatus>('loading')

  useEffect(() => {
    if (!open) return
    setCurrentIndex(clampIndex(initialIndex, frameIds))
    closeButtonRef.current?.focus()
  }, [frameIds, initialIndex, open])

  useEffect(() => {
    if (!open || frameIds.length === 0) return
    setImageStatus('loading')
  }, [currentIndex, frameIds, open])

  useEffect(() => {
    if (!open) return

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        event.preventDefault()
        onClose()
        return
      }

      if (event.key !== 'Tab') return
      const dialog = dialogRef.current
      if (!dialog) return
      const focusable = Array.from(
        dialog.querySelectorAll<HTMLElement>(
          'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
        ),
      ).filter((node) => !node.hasAttribute('hidden'))
      if (focusable.length === 0) return

      const first = focusable[0]
      const last = focusable[focusable.length - 1]
      if (!first || !last) return
      const active = document.activeElement
      if (event.shiftKey && active === first) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && active === last) {
        event.preventDefault()
        first.focus()
      }
    }

    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [onClose, open])

  const currentFrameId = frameIds[currentIndex]
  const currentImageUrl = currentFrameId ? frameImageUrl(lessonId, currentFrameId) : ''
  const frameLabel = currentFrameId ? `Frame ${currentFrameId}` : 'Screenshot'
  const countLabel = frameIds.length > 1 ? `${currentIndex + 1} of ${frameIds.length}` : '1 screenshot'
  const thumbnailUrls = useMemo(
    () => frameIds.map((frameId) => ({ frameId, url: frameImageUrl(lessonId, frameId) })),
    [frameIds, lessonId],
  )

  if (!open || frameIds.length === 0) {
    return null
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 p-4"
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose()
      }}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        data-testid="screenshot-modal"
        className="flex max-h-[90vh] w-full max-w-6xl flex-col overflow-hidden rounded-xl border border-slate-700 bg-slate-950 text-slate-50 shadow-2xl"
      >
        <div className="flex items-center justify-between gap-4 border-b border-slate-800 px-4 py-3">
          <div className="min-w-0">
            <h2 id={titleId} className="truncate text-sm font-semibold">
              {frameLabel}
            </h2>
            <p className="text-xs text-slate-400">{countLabel}</p>
          </div>
          <Button
            ref={closeButtonRef}
            type="button"
            variant="ghost"
            className="h-9 w-9 p-0 text-slate-50 hover:bg-slate-800"
            aria-label="Close screenshot viewer"
            onClick={onClose}
          >
            <X className="h-4 w-4" />
          </Button>
        </div>

        <div className="relative flex min-h-[28rem] flex-1 items-center justify-center bg-slate-900 p-4">
          {frameIds.length > 1 ? (
            <Button
              type="button"
              variant="secondary"
              size="sm"
              className="absolute left-4 top-1/2 z-10 -translate-y-1/2"
              onClick={() => setCurrentIndex((index) => Math.max(0, index - 1))}
              disabled={currentIndex === 0}
              aria-label="Previous screenshot"
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
          ) : null}

          <div className="relative flex h-full w-full items-center justify-center">
            {imageStatus === 'loading' ? <Skeleton className="absolute h-[min(70vh,40rem)] w-full max-w-5xl rounded-xl bg-slate-800" /> : null}
            {imageStatus === 'error' ? (
              <div className="flex h-[min(70vh,40rem)] w-full max-w-5xl flex-col items-center justify-center gap-3 rounded-xl border border-slate-800 bg-slate-900 text-center">
                <ImageIcon className="h-10 w-10 text-slate-500" />
                <div>
                  <p className="text-sm font-medium">Screenshot unavailable</p>
                  <p className="text-xs text-slate-400">The frame image could not be loaded.</p>
                </div>
              </div>
            ) : null}
            <img
              key={currentFrameId}
              src={currentImageUrl}
              alt={`Screenshot for ${frameLabel}`}
              className={cn(
                'max-h-[70vh] w-auto max-w-full rounded-xl object-contain',
                imageStatus === 'loaded' ? 'block' : 'invisible',
              )}
              onLoad={() => setImageStatus('loaded')}
              onError={() => setImageStatus('error')}
            />
          </div>

          {frameIds.length > 1 ? (
            <Button
              type="button"
              variant="secondary"
              size="sm"
              className="absolute right-4 top-1/2 z-10 -translate-y-1/2"
              onClick={() => setCurrentIndex((index) => Math.min(frameIds.length - 1, index + 1))}
              disabled={currentIndex === frameIds.length - 1}
              aria-label="Next screenshot"
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
          ) : null}
        </div>

        {frameIds.length > 1 ? (
          <div className="flex gap-3 overflow-x-auto border-t border-slate-800 px-4 py-4">
            {thumbnailUrls.map(({ frameId, url }, index) => (
              <button
                key={frameId}
                type="button"
                className={cn(
                  'shrink-0 overflow-hidden rounded-lg border transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400',
                  index === currentIndex ? 'border-teal-400' : 'border-slate-700 hover:border-slate-500',
                )}
                aria-label={`Open frame ${frameId}`}
                onClick={() => setCurrentIndex(index)}
              >
                <img src={url} alt={`Thumbnail for frame ${frameId}`} className="h-16 w-24 object-cover" />
              </button>
            ))}
          </div>
        ) : null}
      </div>
    </div>
  )
}
