import { createBrowserRouter, Navigate } from 'react-router-dom';
import { NotFound } from '@/components/common/NotFound';
import { AppShell } from '@/components/layout/AppShell';
import { ConceptPage } from '@/pages/ConceptPage';
import { EvidencePage } from '@/pages/EvidencePage';
import { LessonPage } from '@/pages/LessonPage';
import { RulePage } from '@/pages/RulePage';
import { SearchPage } from '@/pages/SearchPage';

export const router = createBrowserRouter([
  {
    element: <AppShell />,
    children: [
      { index: true, element: <Navigate to="/search" replace /> },
      { path: 'search', element: <SearchPage /> },
      { path: 'rule/:docId', element: <RulePage /> },
      { path: 'evidence/:docId', element: <EvidencePage /> },
      { path: 'concept/:conceptId', element: <ConceptPage /> },
      { path: 'lesson/:lessonId', element: <LessonPage /> },
      { path: '*', element: <NotFound /> },
    ],
  },
]);
