import React, { useEffect, useMemo, useRef, useState } from 'react';
import { ArrowRight, ClipboardCheck, Hourglass, Plus, RefreshCw, RotateCcw, TriangleAlert } from 'lucide-react';
import { api } from '../api/client';
import { useAuth } from '../auth/AuthContext';
import { PLANS_CHANGED, useAsync, useNow } from '../lib/hooks';
import { buildPath, navigate } from '../lib/router';
import { expiresIn, formatDate, formatLKR, relativeTime } from '../lib/format';
import { Badge, Button, Card, Checkbox, EmptyState, ErrorPanel, LoadingBlock, PageHeader, Select, StatusPill, Tabs } from '../components/ui';
import { cn } from '../lib/utils';

export default function ApprovalsPage({ query }) {
  const { user, can } = useAuth();
  const [tab, setTab] = useState(query.tab === 'all' ? 'all' : 'pending');
  const [warningFilter, setWarningFilter] = useState('any');
  const [mine, setMine] = useState(false);
  const now = useNow(30_000);

  const pending = useAsync(() => api.pending(100), []);
  const all = useAsync(() => api.auditLogs({ record_type: 'dispatch_recommendation', limit: 100 }), [], { immediate: tab === 'all' });

  const source = tab === 'pending' ? pending : all;
  const [updatedAt, setUpdatedAt] = useState(Date.now());
  useEffect(() => { if (!source.loading) setUpdatedAt(Date.now()); }, [source.loading]);
  // Stay current when a plan is created or decided elsewhere in the app.
  const refreshRef = useRef(() => {});
  refreshRef.current = () => { pending.reload(); if (all.data) all.reload(); };
  useEffect(() => {
    const refresh = () => refreshRef.current();
    window.addEventListener(PLANS_CHANGED, refresh);
    return () => window.removeEventListener(PLANS_CHANGED, refresh);
  }, []);
  const rows = useMemo(() => {
    let list = source.data || [];
    if (warningFilter === 'with') list = list.filter((r) => r.final_decision?.warnings?.length);
    if (warningFilter === 'without') list = list.filter((r) => !r.final_decision?.warnings?.length);
    if (mine) list = list.filter((r) => r.user_id === user.user_id);
    if (tab === 'pending') list = [...list].sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp)); // soonest expiry first
    return list;
  }, [source.data, warningFilter, mine, tab, user.user_id]);

  const switchTab = (value) => setTab(value); // the "All plans" list loads (and refreshes) when its tab opens

  return (
    <div>
      <PageHeader
        title="Approvals"
        description={can('audit:approve') ? 'Plans waiting for your decision. Plans expire 24 hours after they are created.' : 'Plans waiting for a facility manager. You can open any plan to read it.'}
        actions={can('optimizer:run') && <Button icon={Plus} onClick={() => navigate('/plans/new')}>New dispatch plan</Button>}
      />

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <Tabs label="Plan list" value={tab} onChange={switchTab}
          tabs={[{ value: 'pending', label: 'Pending', count: pending.data?.length }, { value: 'all', label: 'All plans' }]} />
        <label className="sr-only" htmlFor="warning-filter">Warnings</label>
        <Select id="warning-filter" value={warningFilter} onChange={(e) => setWarningFilter(e.target.value)} className="w-auto">
          <option value="any">Any warnings</option>
          <option value="with">Has warnings</option>
          <option value="without">No warnings</option>
        </Select>
        <Checkbox id="mine" checked={mine} onChange={setMine}>Created by me</Checkbox>
        <div className="ml-auto flex items-center gap-2 text-xs text-ink-2">
          <span aria-live="polite">Updated {relativeTime(new Date(updatedAt).toISOString(), now)}</span>
          <Button size="sm" variant="ghost" icon={RefreshCw} loading={source.loading} onClick={source.reload}>Refresh</Button>
        </div>
      </div>

      <Card bodyClassName="p-0">
        {source.error && <div className="p-4"><ErrorPanel error={source.error} onRetry={source.reload} /></div>}
        {source.loading && !source.data ? <LoadingBlock /> : rows.length === 0 ? (
          <EmptyState icon={ClipboardCheck} title={tab === 'pending' ? 'Nothing waiting for approval.' : 'No plans yet.'}>
            {can('orchestrator:query') && 'Ask CampusGrid to plan tomorrow, and the plan will appear here.'}
          </EmptyState>
        ) : (
          <>
            <div className="hidden border-b border-line bg-surface-2 px-5 py-2 text-xs font-medium uppercase tracking-wide text-ink-2 md:grid md:grid-cols-[minmax(0,1.4fr)_repeat(3,minmax(0,1fr))_auto] md:gap-3" aria-hidden>
              <span>Plan</span><span>Savings</span><span>Warnings</span><span>{tab === 'pending' ? 'Expires' : 'Status'}</span><span className="w-20" />
            </div>
          <ul className={cn('divide-y divide-line', source.loading && 'opacity-60')}>
            {rows.map((r) => <PlanRow key={r.log_id} row={r} now={now} canApprove={can('audit:approve')} canRerun={can('orchestrator:query')} />)}
          </ul>
          </>
        )}
      </Card>
    </div>
  );
}

function PlanRow({ row, now, canApprove, canRerun }) {
  const d = row.final_decision || {};
  const warnings = d.warnings?.length || 0;
  const expiry = expiresIn(row.timestamp, 24, now);
  const status = row.effective_status;
  return (
    <li className="grid gap-3 px-5 py-4 md:grid-cols-[minmax(0,1.4fr)_repeat(3,minmax(0,1fr))_auto] md:items-center">
      <div className="min-w-0">
        <p className="font-medium text-ink">Plan #{row.log_id} · {d.target?.room || '—'}</p>
        <p className="truncate text-sm text-ink-2">{formatDate(d.target?.date)} · by {row.user_id} · {relativeTime(row.timestamp)}</p>
      </div>
      <div className="text-sm"><span className="text-ink-2 md:hidden">Savings </span><span className="font-medium text-ink">{formatLKR(d.net_savings_lkr)}</span></div>
      <div>{warnings ? <Badge tone="warning" icon={TriangleAlert}>{warnings} warning{warnings > 1 ? 's' : ''}</Badge> : <span className="text-sm text-ink-2">No warnings</span>}</div>
      <div>
        {status === 'pending'
          ? <Badge tone={expiry.ms < 3 * 3600_000 ? 'warning' : 'neutral'} icon={Hourglass}>Expires in {expiry.label}</Badge>
          : <StatusPill status={status} />}
      </div>
      <div className="flex gap-2 md:w-20 md:justify-end">
        {status === 'expired' && canRerun ? (
          <Button size="sm" variant="secondary" icon={RotateCcw} onClick={() => navigate(buildPath('/ask', { q: row.query_text }))}>Re-run</Button>
        ) : (
          <Button size="sm" variant={status === 'pending' && canApprove ? 'primary' : 'secondary'} icon={ArrowRight}
            onClick={() => navigate(`/plans/${row.log_id}`)}>
            {status === 'pending' && canApprove ? 'Review' : 'View'}
          </Button>
        )}
      </div>
    </li>
  );
}
