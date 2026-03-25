import { createBrowserRouter, Navigate } from 'react-router-dom';

import { NotFound } from '@/components/common/NotFound';
import { AppShell } from '@/components/layout/AppShell';
import { CompareLessonsPage } from '@/pages/CompareLessonsPage';
import { CompareRulesPage } from '@/pages/CompareRulesPage';
import { ConceptLessonsPage } from '@/pages/ConceptLessonsPage';
import { ConceptPage } from '@/pages/ConceptPage';
import { ConceptRulesPage } from '@/pages/ConceptRulesPage';
import { EvidencePage } from '@/pages/EvidencePage';
import { LessonPage } from '@/pages/LessonPage';
import { RelatedRulesPage } from '@/pages/RelatedRulesPage';
import { ReviewComparePage } from '@/pages/ReviewComparePage';
import { ReviewItemPage } from '@/pages/ReviewItemPage';
import { ReviewQueuePage } from '@/pages/ReviewQueuePage';
import { RulePage } from '@/pages/RulePage';
import { SearchPage } from '@/pages/SearchPage';

export const router = createBrowserRouter([
  {
    element: <AppShell />,
    children: [
      { index: true, element: <Navigate to="/search" replace /> },
      { path: 'search', element: <SearchPage /> },
      { path: 'compare/rules', element: <CompareRulesPage /> },
      { path: 'compare/lessons', element: <CompareLessonsPage /> },
      { path: 'rule/:docId', element: <RulePage /> },
      { path: 'rule/:docId/related', element: <RelatedRulesPage /> },
      { path: 'evidence/:docId', element: <EvidencePage /> },
      { path: 'concept/:conceptId', element: <ConceptPage /> },
      { path: 'concept/:conceptId/rules', element: <ConceptRulesPage /> },
      { path: 'concept/:conceptId/lessons', element: <ConceptLessonsPage /> },
      { path: 'lesson/:lessonId', element: <LessonPage /> },
      { path: 'review/queue', element: <ReviewQueuePage /> },
      { path: 'review/item/:targetType/:targetId', element: <ReviewItemPage /> },
      { path: 'review/compare', element: <ReviewComparePage /> },
      { path: '*', element: <NotFound /> },
    ],
  },
]);
