import React, { Suspense, lazy, useEffect } from 'react';
import { AuthProvider, useAuth } from './auth/AuthContext';
import { AppLayout } from './components/Layout';
import { EmptyState, LoadingBlock, NotAllowed } from './components/ui';
import { matchPath, navigate, buildPath, useRoute } from './lib/router';
import LoginPage from './pages/LoginPage';
import { PageErrorBoundary, ToastProvider } from './components/feedback';

// Pages load on demand, so signing in does not download every screen (or the chart library) up front.
const OverviewPage = lazy(() => import('./pages/OverviewPage'));
const AskPage = lazy(() => import('./pages/AskPage'));
const ApprovalsPage = lazy(() => import('./pages/ApprovalsPage'));
const NewPlanPage = lazy(() => import('./pages/NewPlanPage'));
const PlanReviewPage = lazy(() => import('./pages/PlanReviewPage'));
const WhatIfPage = lazy(() => import('./pages/WhatIfPage'));
const ForecastPage = lazy(() => import('./pages/ForecastPage'));
const RegulationsSearchPage = lazy(() => import('./pages/RegulationsSearchPage'));
const LibraryPage = lazy(() => import('./pages/LibraryPage'));
const AuditPage = lazy(() => import('./pages/AuditPage'));
const AnalyticsPage = lazy(() => import('./pages/AnalyticsPage'));
const SystemStatusPage = lazy(() => import('./pages/SystemStatusPage'));

// Order matters: '/plans/new' must be matched before '/plans/:id'.
const ROUTES = [
  { pattern: '/', page: OverviewPage, title: 'Overview' },
  { pattern: '/ask', page: AskPage, permission: 'orchestrator:query', title: 'Ask CampusGrid' },
  { pattern: '/plans', page: ApprovalsPage, permission: 'audit:read', title: 'Approvals' },
  { pattern: '/plans/new', page: NewPlanPage, permission: 'optimizer:run', title: 'New dispatch plan' },
  { pattern: '/plans/:id', page: PlanReviewPage, permission: 'audit:read', title: 'Plan review' },
  { pattern: '/what-if', page: WhatIfPage, permission: 'simulation:run', title: 'What-if simulator' },
  { pattern: '/forecast', page: ForecastPage, permission: 'telemetry:read', title: 'Forecast' },
  { pattern: '/regulations', page: RegulationsSearchPage, permission: 'rag:search', title: 'Regulation search' },
  { pattern: '/regulations/library', page: LibraryPage, permission: 'rag:search', title: 'Regulation library' },
  { pattern: '/audit', page: AuditPage, permission: 'audit:read', title: 'Audit & Compliance' },
  { pattern: '/analytics', page: AnalyticsPage, permission: 'analytics:read', title: 'Analytics' },
  { pattern: '/system', page: SystemStatusPage, permission: 'system:read', title: 'System status' },
];

function Redirect({ to }) {
  useEffect(() => { navigate(to, { replace: true }); }, [to]);
  return null;
}

function Screen() {
  const route = useRoute();
  const { status, can, homePath } = useAuth();

  let matched = null;
  for (const r of ROUTES) {
    const params = matchPath(r.pattern, route.path);
    if (params) { matched = { ...r, params }; break; }
  }

  useEffect(() => {
    document.title = route.path === '/login' ? 'Sign in · CampusGrid AI' : `${matched?.title || 'Not found'} · CampusGrid AI`;
    window.scrollTo(0, 0);
    document.getElementById('main')?.focus({ preventScroll: true });
  }, [route.path, matched?.title]);

  if (status === 'checking') return <div className="flex h-full items-center justify-center"><LoadingBlock label="Checking your session…" /></div>;

  if (route.path === '/login') {
    if (status === 'signed_in') return <Redirect to={route.query.next || homePath} />;
    return <LoginPage next={route.query.next} />;
  }
  if (status !== 'signed_in') return <Redirect to={buildPath('/login', { next: route.full === '/' ? undefined : route.full })} />;

  let content;
  if (!matched) {
    content = <EmptyState title="Page not found">The address may be mistyped. <a className="text-accent-text underline" href={`#${homePath}`}>Go to your home page</a>.</EmptyState>;
  } else if (!can(matched.permission)) {
    content = <NotAllowed />;
  } else {
    const Page = matched.page;
    content = (
      <PageErrorBoundary key={route.path}>
        <Suspense fallback={<LoadingBlock label="Opening…" />}>
          <div className="cg-page"><Page params={matched.params} query={route.query} /></div>
        </Suspense>
      </PageErrorBoundary>
    );
  }
  return <AppLayout path={route.path}>{content}</AppLayout>;
}

export default function App() {
  return (
    <AuthProvider>
      <ToastProvider>
        <Screen />
      </ToastProvider>
    </AuthProvider>
  );
}

