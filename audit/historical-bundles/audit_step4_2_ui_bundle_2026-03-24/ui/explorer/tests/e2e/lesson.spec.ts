import { expect, test } from '@playwright/test'
import { Actor } from './screenplay/actor'
import { LessonDetailPage } from './screenplay/questions/lesson-detail-page'
import { OpenLessonDetail } from './screenplay/tasks/open-lesson-detail'
import type { LessonDetailResponse } from '@/lib/api/types'
import { loadFixture, mockJsonRoute } from './support/browser-fixtures'

const lessonDetail = loadFixture<LessonDetailResponse>('lesson-detail.json')
const lessonId = lessonDetail.lesson_id

test('open lesson detail directly', async ({ page }) => {
  await mockJsonRoute(page, '**/browser/lesson/**', lessonDetail)

  const analyst = new Actor('Analyst', page)
  await analyst.attemptsTo(OpenLessonDetail(lessonId))
  expect(await analyst.asks(LessonDetailPage.lessonHeading)).toContain(lessonId)
  expect(await analyst.asks(LessonDetailPage.hasCopyLink)).toBe(true)
  expect(await analyst.asks(LessonDetailPage.hasSupportBasisDistribution)).toBe(true)
  expect(await analyst.asks(LessonDetailPage.hasTopConcepts)).toBe(true)
  expect(await analyst.asks(LessonDetailPage.topRuleCount)).toBeGreaterThan(0)
})
