export function frameImageUrl(lessonId: string, frameKey: string): string {
  return `/browser/frame/${encodeURIComponent(lessonId)}/${encodeURIComponent(frameKey)}`
}
