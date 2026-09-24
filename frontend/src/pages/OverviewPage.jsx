import React from 'react';
import { ArrowRight, BookOpen, CheckCircle2, ClipboardCheck, MessageSquare, ShieldCheck, Thermometer, TriangleAlert, XCircle } from 'lucide-react';
import { api } from '../api/client';
import { useAuth } from '../auth/AuthContext';
import { useAsync } from '../lib/hooks';
import { buildPath, navigate } from '../lib/router';
import { formatDate, formatDateTime, formatKw, formatLKR, formatNumber, formatPct, relativeTime, tomorrowIso } from '../lib/format';
import { ForecastChart } from '../components/charts';
import { Banner, Button, Card, EmptyState, ErrorPanel, LoadingBlock, PageHeader, StatTile } from '../components/ui';

export default function OverviewPage() {
  const { can } = useAuth();
  return (
    <div>
      <PageHeader title={`Good ${greeting()}`} description="What needs attention today." />
      {can('orchestrator:query') ? <PlannerOverview /> : <AuditorOverview />}
    </div>
  );
}

function greeting() {
  const hour = Number(new Intl.DateTimeFormat('en-GB', { timeZone: 'Asia/Colombo', hour: 'numeric', hour12: false }).format(new Date()));
  return hour < 12 ? 'morning' : hour < 17 ? 'afternoon' : 'evening';
}

function peakOf(values = [], slots = []) {
  if (!values.length) return { value: null, slot: null };
  let i = 0;
  values.forEach((v, idx) => { if (v > values[i]) i = idx; });
  return { value: values[i], slot: slots[i] };
}

function PlannerOverview() {
  const { can } = useAuth();
  const tomorrow = tomorrowIso();
  const pending = useAsync(() => api.pending(100), []);
  const forecast = useAsync(() => api.forecast(tomorrow, 'LH-1'), [tomorrow]);
  const lastApproved = useAsync(() => api.auditLogs({ record_type: 'dispatch_recommendation', status: 'approved', limit: 1 }), []);

  const pendingRows = pending.data || [];
  const oldest = pendingRows.reduce((acc, r) => (!acc || r.timestamp < acc ? r.timestamp : acc), null);
  const f = forecast.data;
  const peak = peakOf(f?.forecast_demand_kw, f?.time_slots);
  const last = lastApproved.data?.[0];
  const isManager = can('audit:approve');

  return (
    <div className="space-y-6">
      <div className="grid gap-4 lg:grid-cols-3">
        <Card title="Pending approvals" actions={pendingRows.length > 0 && (
          <Button size="sm" variant={isManager ? 'primary' : 'secondary'} icon={ArrowRight} onClick={() => navigate('/plans')}>{isManager ? 'Review' : 'View'}</Button>
        )}>
          {pending.error ? <ErrorPanel error={pending.error} onRetry={pending.reload} /> : pending.loading && !pending.data ? <LoadingBlock /> : (
            <>
              <p className="text-5xl font-semibold text-ink">{pendingRows.length}</p>
              <p className="mt-1 text-sm text-ink-2">{pendingRows.length ? `Oldest waiting ${relativeTime(oldest)} · plans expire after 24 h` : 'Nothing waiting for approval.'}</p>
            </>
          )}
        </Card>
        <Card title="Tomorrow at a glance" description={formatDate(tomorrow)}>
          {forecast.error ? <ErrorPanel error={forecast.error} onRetry={forecast.reload} /> : forecast.loading && !f ? <LoadingBlock /> : (
            <>
              <p className="text-2xl font-semibold text-ink">{formatKw(peak.value)} <span className="text-base font-normal text-ink-2">peak at {peak.slot}</span></p>
              <p className="mt-1 text-sm text-ink-2">{formatNumber(f?.anomaly_count)} half-hours flagged as unusually high</p>
            </>
          )}
        </Card>
        <Card title="Last approved plan">
          {lastApproved.error ? <ErrorPanel error={lastApproved.error} onRetry={lastApproved.reload} /> : lastApproved.loading && !lastApproved.data ? <LoadingBlock /> : last ? (
            <button type="button" onClick={() => navigate(`/plans/${last.log_id}`)} className="w-full text-left">
              <p className="text-2xl font-semibold text-ink">{formatLKR(last.final_decision?.net_savings_lkr)}</p>
              <p className="mt-1 text-sm text-ink-2">
                {formatPct(last.final_decision?.savings_percentage)} saving · peak −{formatKw(last.final_decision?.peak_shaved_kw, 0)}
              </p>
              <p className="mt-1 text-xs text-ink-2">Plan #{last.log_id} · approved by {last.decision?.decided_by} · {formatDateTime(last.decision?.decided_at)}</p>
            </button>
          ) : (
            <EmptyState icon={ClipboardCheck} title="No plans approved yet."
              action={<Button size="sm" icon={MessageSquare} onClick={() => navigate(buildPath('/ask', { q: "Plan tomorrow's battery schedule to cut the evening peak" }))}>Plan tomorrow</Button>}>
              Ask CampusGrid to plan tomorrow's battery schedule.
            </EmptyState>
          )}
        </Card>
      </div>

      {f && (
        <Card title="Tomorrow's demand" description="Lecture Hall 1 timetable · campus-wide demand and solar">
          {f.forecast_summary && <p className="mb-4 text-sm text-ink">{f.forecast_summary}</p>}
          <ForecastChart slots={f.time_slots} demand={f.forecast_demand_kw} solar={f.forecast_solar_kw} lower={f.lower_bound_kw} upper={f.upper_bound_kw} />
        </Card>
      )}

      <Card title="Quick actions">
        <div className="flex flex-wrap gap-2">
          <Button icon={MessageSquare} onClick={() => navigate(buildPath('/ask', { q: "Plan tomorrow's battery schedule to cut the evening peak" }))}>Plan tomorrow</Button>
          {can('simulation:run') && <Button variant="secondary" icon={Thermometer} onClick={() => navigate('/what-if')}>Run a what-if</Button>}
          <Button variant="secondary" icon={BookOpen} onClick={() => navigate('/regulations')}>Look up a rule</Button>
        </div>
      </Card>
    </div>
  );
}

function AuditorOverview() {
  const decisions = useAsync(() => api.auditLogs({ record_type: 'approval_decision', limit: 5 }), []);
  const integrity = useAsync(() => api.verifyAudit(), []);
  const approved = useAsync(() => api.auditLogs({ record_type: 'dispatch_recommendation', status: 'approved', limit: 100 }), []);

  const month = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Colombo', year: 'numeric', month: '2-digit' }).format(new Date());
  const withWarnings = (approved.data || []).filter((r) => r.final_decision?.warnings?.length
    && new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Colombo', year: 'numeric', month: '2-digit' }).format(new Date(r.timestamp)) === month);

  return (
    <div className="space-y-6">
      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Audit integrity" actions={<Button size="sm" variant="secondary" icon={ShieldCheck} onClick={integrity.reload} loading={integrity.loading}>Verify again</Button>}>
          {integrity.error ? <ErrorPanel error={integrity.error} /> : integrity.loading && !integrity.data ? <LoadingBlock /> : integrity.data?.valid ? (
            <Banner tone="success" icon={CheckCircle2} title={`All ${integrity.data.records_checked} records verified`}>Every signature matches its content and the record before it.</Banner>
          ) : integrity.data ? (
            <Banner tone="critical" icon={XCircle} title={`Record #${integrity.data.first_invalid_log_id} does not match its signature`}>The trail may have been altered.</Banner>
          ) : null}
        </Card>
        <StatTile label="Plans approved with warnings this month" value={approved.loading && !approved.data ? '…' : withWarnings.length}
          sub={withWarnings.length ? 'Each approval recorded that the warnings were acknowledged.' : 'None this month.'} />
      </div>

      <Card title="Recent decisions" actions={<Button size="sm" variant="secondary" icon={ArrowRight} onClick={() => navigate('/audit')}>Full audit trail</Button>} bodyClassName="p-0">
        {decisions.error ? <div className="p-4"><ErrorPanel error={decisions.error} /></div> : decisions.loading && !decisions.data ? <LoadingBlock /> : !decisions.data?.length ? (
          <EmptyState title="No decisions recorded yet." />
        ) : (
          <ul className="divide-y divide-line">
            {decisions.data.map((d) => (
              <li key={d.log_id}>
                <button type="button" onClick={() => navigate(`/plans/${d.parent_log_id}`)} className="flex w-full items-center justify-between gap-3 px-5 py-3 text-left hover:bg-surface-2">
                  <span className="min-w-0">
                    <span className="flex items-center gap-1.5 text-sm font-medium text-ink">
                      {d.approval_status === 'approved' ? <CheckCircle2 className="h-4 w-4 text-good-text" aria-hidden /> : <XCircle className="h-4 w-4 text-ink-2" aria-hidden />}
                      Plan #{d.parent_log_id} {d.approval_status} by {d.user_id}
                    </span>
                    {d.final_decision?.acknowledged_warnings?.length > 0 && (
                      <span className="mt-0.5 flex items-center gap-1 text-xs text-warn-text"><TriangleAlert className="h-3.5 w-3.5" aria-hidden />{d.final_decision.acknowledged_warnings.length} warning(s) acknowledged</span>
                    )}
                  </span>
                  <span className="shrink-0 text-xs text-ink-2">{formatDateTime(d.timestamp)}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
