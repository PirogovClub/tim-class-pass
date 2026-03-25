import { ImageIcon } from 'lucide-react'
import { useState } from 'react'

import { ScreenshotModal } from '@/components/common/ScreenshotModal'
import { Button } from '@/components/ui/button'
import { frameImageUrl } from '@/lib/utils/frames'

type VisualSummarySectionProps = {
  visualSummary: string
  lessonId: string
  frameIds: string[]
}

export function VisualSummarySection({ visualSummary, lessonId, frameIds }: VisualSummarySectionProps) {
  const [open, setOpen] = useState(false)
  const [previewFailed, setPreviewFailed] = useState(false)
  const hasFrames = frameIds.length > 0
  const previewFrameId = frameIds[0]
  const previewUrl = previewFrameId ? frameImageUrl(lessonId, previewFrameId) : null
  const buttonLabel = frameIds.length > 1 ? `View ${frameIds.length} screenshots` : 'View screenshot'

  return (
    <>
      <section className="rounded-xl border border-slate-200 bg-white p-5" data-testid="visual-summary-section">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0 flex-1">
            <h2 className="text-lg font-semibold text-slate-900">Visual Summary</h2>
            <p className="mt-2 text-sm text-slate-700">{visualSummary}</p>
          </div>
          {hasFrames ? (
            <Button
              type="button"
              variant="outline"
              className="shrink-0"
              onClick={() => setOpen(true)}
              aria-label={buttonLabel}
            >
              <ImageIcon className="mr-2 h-4 w-4" />
              {buttonLabel}
            </Button>
          ) : null}
        </div>

        {hasFrames && previewUrl ? (
          <button
            type="button"
            data-testid="visual-summary-preview"
            aria-label="Open screenshot preview"
            className="mt-4 flex w-full items-center gap-4 rounded-xl border border-slate-200 bg-slate-50 p-3 text-left transition-colors hover:bg-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400"
            onClick={() => setOpen(true)}
          >
            {previewFailed ? (
              <div className="flex h-20 w-32 shrink-0 items-center justify-center rounded-lg bg-slate-200 text-slate-500">
                <ImageIcon className="h-7 w-7" />
              </div>
            ) : (
              <img
                src={previewUrl}
                alt={`Preview for frame ${previewFrameId}`}
                className="h-20 w-32 shrink-0 rounded-lg object-cover"
                onError={() => setPreviewFailed(true)}
              />
            )}
            <div className="min-w-0">
              <p className="text-sm font-medium text-slate-900">{buttonLabel}</p>
              <p className="mt-1 text-xs text-slate-500">
                {frameIds.length > 1 ? `Starts with frame ${previewFrameId}` : `Frame ${previewFrameId}`}
              </p>
            </div>
          </button>
        ) : null}
      </section>

      <ScreenshotModal open={open} onClose={() => setOpen(false)} lessonId={lessonId} frameIds={frameIds} />
    </>
  )
}
