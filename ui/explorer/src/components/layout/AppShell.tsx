import { Outlet } from 'react-router-dom';

import { CompareLaunchBar } from '@/components/compare/CompareLaunchBar';
import { TopBar } from '@/components/layout/TopBar';
import { useCompareSelection } from '@/hooks/useCompareSelection';

export function AppShell() {
  const ruleSelection = useCompareSelection('rules')
  const lessonSelection = useCompareSelection('lessons')

  return <div className="min-h-screen bg-slate-50 text-slate-950"><a href="#main-content" className="sr-only absolute left-4 top-4 rounded bg-white px-3 py-2 text-sm font-medium shadow focus:not-sr-only">Skip to content</a><TopBar /><CompareLaunchBar kind="rules" ids={ruleSelection.ids} onClear={ruleSelection.clear} /><CompareLaunchBar kind="lessons" ids={lessonSelection.ids} onClear={lessonSelection.clear} /><main id="main-content"><Outlet /></main></div>;
}
