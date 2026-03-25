import { Outlet } from 'react-router-dom';
import { TopBar } from '@/components/layout/TopBar';

export function AppShell() {
  return <div className="min-h-screen bg-slate-50 text-slate-950"><a href="#main-content" className="sr-only absolute left-4 top-4 rounded bg-white px-3 py-2 text-sm font-medium shadow focus:not-sr-only">Skip to content</a><TopBar /><main id="main-content"><Outlet /></main></div>;
}
