import React, { useEffect, useMemo, useState } from 'react';
import { ArrowRight, CheckCircle2, Download, ShieldAlert, ShieldCheck, XCircle } from 'lucide-react';
import { api } from '../api/client';
import { useAuth } from '../auth/AuthContext';
import { useAsync } from '../lib/hooks';
import { navigate } from '../lib/router';
import { formatDateTime, INTENT_LABELS, RECORD_TYPE_LABELS, utcTitle } from '../lib/format';
import {
  Banner, Button, Card, Disclosure, Drawer, EmptyState, ErrorPanel, Field, KeyValue, LoadingBlock, PageHeader, Select,
  StatusPill, TextInput,
} from '../components/ui';
import { cn } from '../lib/utils';

const STATUS_OPTIONS = ['pending', 'approved', 'rejected', 'expired', 'not_required'];
const AGENT_STEPS = [
  ['agent1_telemetry', 'Agent 1 · Forecast'],
  ['agent2_digital_twin', 'Agent 2 · Comfort check'],
  ['agent3_policy_rag', 'Agent 3 · Regulations'],
  ['agent4_dispatch', 'Agent 4 · Plan & explanation'],
];

function toCsv(rows) {
  const header = ['log_id', 'timestamp_utc', 'user_id', 'record_type', 'status', 'question'];
  const escape = (v) => `"${String(v ?? '').replace(/"/g, '""')}"`;
  return [header.join(','), ...rows.map((r) => [r.log_id, r.timestamp, r.user_id, r.record_type, r.effective_status, r.query_text].map(escape).join(','))].join('\n');
}

export default function AuditPage({ query }) {
  const { can } = useAuth();
  const [filters, setFilters] = useState({ type: '', status: '', user: '', from: '', to: '' });
  const [openId, setOpenId] = useState(query.open ? Number(query.open) : null);
  const [verify, setVerify] = useState({ busy: false, result: null, error: null });

  const logs = useAsync(() => api.auditLogs({ limit: 100, record_type: filters.type || undefined, status: filters.status || undefined }), [filters.type, filters.status]);

  const rows = useMemo(() => (logs.data || []).filter((r) => {
    if (filters.user && !r.user_id.toLowerCase().includes(filters.user.toLowerCase())) return false;
    const day = r.timestamp.slice(0, 10);
    if (filters.from && day < filters.from) return false;
    if (filters.to && day > filters.to) return false;
    return true;
  }), [logs.data, filters.user, filters.from, filters.to]);

  const set = (key) => (e) => setFilters((f) => ({ ...f, [key]: e.target.value }));

  async function runVerify() {
    setVerify({ busy: true, result: null, error: null });
    try { setVerify({ busy: false, result: await api.verifyAudit(), error: null }); }
    catch (error) { setVerify({ busy: false, result: null, error }); }
  }

  function exportCsv() {
    const blob = new Blob([toCsv(rows)], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `campusgrid-audit-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  return (
    <div>
      <PageHeader
        title="Audit & Compliance"
        description="Every question, plan, decision and document upload, in an append-only trail. Each record is signed and chained to the one before it."
        actions={(
          <>
            {can('analytics:read') && <Button variant="secondary" icon={ShieldCheck} loading={verify.busy} onClick={runVerify}>Verify audit trail</Button>}
            <Button variant="secondary" icon={Download} onClick={exportCsv} disabled={!rows.length}>Export CSV</Button>
          </>
        )}
      />

      {verify.error && <ErrorPanel error={verify.error} className="mb-4" />}
      {verify.result && (verify.result.valid ? (
        <Banner tone="success" icon={CheckCircle2} className="mb-4" title={`All ${verify.result.records_checked} records verified`} onDismiss={() => setVerify({ busy: false, result: null, error: null })}>
          Every signature matches its content and the record before it.{verify.result.unsigned_legacy_records ? ` ${verify.result.unsigned_legacy_records} older unsigned records were not checked.` : ''}
        </Banner>
      ) : (
        <Banner tone="critical" icon={XCircle} className="mb-4" title={`Record #${verify.result.first_invalid_log_id} does not match its signature`}>
          The trail may have been altered at or after this record. Preserve the database and report it.
        </Banner>
      ))}

      <Card bodyClassName="p-0">
        <div className="grid gap-3 border-b border-line p-4 sm:grid-cols-2 lg:grid-cols-5">
          <Field label="Type" htmlFor="f-type">
            <Select id="f-type" value={filters.type} onChange={set('type')}>
              <option value="">All types</option>
              {Object.entries(RECORD_TYPE_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </Select>
          </Field>
          <Field label="Status" htmlFor="f-status">
            <Select id="f-status" value={filters.status} onChange={set('status')}>
              <option value="">Any status</option>
              {STATUS_OPTIONS.map((s) => <option key={s} value={s}>{s.replace('_', ' ')}</option>)}
            </Select>
          </Field>
          <Field label="User" htmlFor="f-user"><TextInput id="f-user" value={filters.user} onChange={set('user')} placeholder="e.g. operator" /></Field>
          <Field label="From" htmlFor="f-from"><TextInput id="f-from" type="date" value={filters.from} onChange={set('from')} /></Field>
          <Field label="To" htmlFor="f-to"><TextInput id="f-to" type="date" value={filters.to} onChange={set('to')} /></Field>
        </div>

        {logs.error && <div className="p-4"><ErrorPanel error={logs.error} onRetry={logs.reload} /></div>}
        {logs.loading && !logs.data ? <LoadingBlock /> : rows.length === 0 ? (
          <EmptyState title="No records match these filters." />
        ) : (
          <div className={cn('overflow-x-auto', logs.loading && 'opacity-60')}>
            <table className="w-full text-sm">
              <caption className="sr-only">Audit records, newest first</caption>
              <thead className="bg-surface-2 text-left text-xs uppercase tracking-wide text-ink-2">
                <tr>
                  <th scope="col" className="px-4 py-2 font-medium">#</th>
                  <th scope="col" className="px-4 py-2 font-medium">Time (Colombo)</th>
                  <th scope="col" className="px-4 py-2 font-medium">User</th>
                  <th scope="col" className="px-4 py-2 font-medium">Type</th>
                  <th scope="col" className="px-4 py-2 font-medium">Question / summary</th>
                  <th scope="col" className="px-4 py-2 font-medium">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {rows.map((r) => (
                  <tr key={r.log_id} className="cursor-pointer hover:bg-surface-2" onClick={() => setOpenId(r.log_id)}>
                    <td className="px-4 py-2.5 tabular">
                      <button type="button" className="font-medium text-accent-text hover:underline" onClick={(e) => { e.stopPropagation(); setOpenId(r.log_id); }}>
                        {r.log_id}
                      </button>
                    </td>
                    <td className="whitespace-nowrap px-4 py-2.5 text-ink-2" title={utcTitle(r.timestamp)}>{formatDateTime(r.timestamp)}</td>
                    <td className="px-4 py-2.5 text-ink">{r.user_id}</td>
                    <td className="whitespace-nowrap px-4 py-2.5 text-ink">{RECORD_TYPE_LABELS[r.record_type] || r.record_type}</td>
                    <td className="max-w-md truncate px-4 py-2.5 text-ink-2" title={r.query_text}>{r.query_text}</td>
                    <td className="px-4 py-2.5"><StatusPill status={r.effective_status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <RecordDrawer id={openId} onClose={() => setOpenId(null)} onOpen={setOpenId} />
    </div>
  );
}

function RecordDrawer({ id, onClose, onOpen }) {
  const [state, setState] = useState({ loading: false, record: null, error: null });

  useEffect(() => {
    if (!id) return;
    let alive = true;
    setState({ loading: true, record: null, error: null });
    api.auditRecord(id)
      .then((record) => alive && setState({ loading: false, record, error: null }))
      .catch((error) => alive && setState({ loading: false, record: null, error }));
    return () => { alive = false; };
  }, [id]);

  const r = state.record;
  const d = r?.final_decision || {};
  const intent = d.intent || {};

  return (
    <Drawer open={Boolean(id)} title={`Record #${id}`} onClose={onClose}>
      {state.loading && <LoadingBlock />}
      {state.error && <ErrorPanel error={state.error} />}
      {r && (
        <div className="space-y-6">
          <div className="flex flex-wrap items-center gap-2">
            <StatusPill status={r.effective_status} />
            <span className="text-sm text-ink-2">{RECORD_TYPE_LABELS[r.record_type] || r.record_type}</span>
          </div>
          <KeyValue items={[
            { label: 'Time', value: <span title={utcTitle(r.timestamp)}>{formatDateTime(r.timestamp)}</span> },
            { label: 'User', value: r.user_id },
            { label: 'Question', value: r.query_text },
            intent.action && { label: 'Understood as', value: `${INTENT_LABELS[intent.action] || intent.action}${intent.room ? ` · ${intent.room}` : ''}${intent.date ? ` · ${intent.date}` : ''}${intent.intent_source === 'llm_router' ? ' (interpreted by AI)' : ''}` },
            d.security_flags?.length && { label: 'Security flags', value: d.security_flags.join(', ') },
          ]} />

          {r.record_type === 'dispatch_recommendation' && (
            <div className="space-y-3">
              {r.decision ? (
                <Banner tone={r.decision.status === 'approved' ? 'success' : 'neutral'} title={`${r.decision.status === 'approved' ? 'Approved' : 'Rejected'} by ${r.decision.decided_by} · ${formatDateTime(r.decision.decided_at)}`}>
                  {r.decision.notes && <p>“{r.decision.notes}”</p>}
                  <button type="button" className="mt-1 text-sm font-medium text-accent-text hover:underline" onClick={() => onOpen(r.decision.decision_log_id)}>Open decision record #{r.decision.decision_log_id}</button>
                </Banner>
              ) : null}
              <Button variant="secondary" icon={ArrowRight} onClick={() => navigate(`/plans/${r.log_id}`)}>Open plan review</Button>
            </div>
          )}
          {r.record_type === 'approval_decision' && r.parent_log_id && (
            <Button variant="secondary" icon={ArrowRight} onClick={() => onOpen(r.parent_log_id)}>Open the plan this decides (#{r.parent_log_id})</Button>
          )}

          {Object.keys(r.agent_sequence || {}).length > 0 && (
            <div className="space-y-2">
              <h3 className="text-sm font-semibold text-ink">Agent steps</h3>
              {AGENT_STEPS.filter(([key]) => r.agent_sequence[key]).map(([key, label]) => {
                const step = r.agent_sequence[key];
                return (
                  <Disclosure key={key} summary={(
                    <span className="flex flex-wrap items-center gap-2">
                      {step.success ? <CheckCircle2 className="h-4 w-4 text-good-text" aria-hidden /> : <XCircle className="h-4 w-4 text-critical-text" aria-hidden />}
                      {label}
                      <span className="text-xs font-normal text-ink-2">{step.success ? 'succeeded' : 'failed'} in {Math.round(step.execution_time_ms)} ms</span>
                    </span>
                  )}>
                    {step.error && <p className="mb-2 text-sm text-critical-text">{step.error}</p>}
                    <pre className="max-h-72 overflow-auto rounded-lg bg-surface-2 p-3 text-xs text-ink">{JSON.stringify(step.data, null, 2)}</pre>
                  </Disclosure>
                );
              })}
            </div>
          )}

          <Disclosure summary="Final decision (as recorded)">
            <pre className="max-h-72 overflow-auto rounded-lg bg-surface-2 p-3 text-xs text-ink">{JSON.stringify(r.final_decision, null, 2)}</pre>
          </Disclosure>

          <div className="space-y-2 rounded-lg border border-line p-3">
            <p className="flex items-center gap-1.5 text-sm font-semibold text-ink">
              {r.signature ? <ShieldCheck className="h-4 w-4 text-good-text" aria-hidden /> : <ShieldAlert className="h-4 w-4 text-warn-text" aria-hidden />}
              {r.signature ? 'Signed record' : 'Unsigned (created before signing was introduced)'}
            </p>
            {r.signature && (
              <KeyValue items={[
                { label: 'Signature (SHA-256)', value: <span className="break-all font-mono text-xs">{r.signature}</span> },
                { label: 'Previous record signature', value: <span className="break-all font-mono text-xs">{r.previous_signature || '— (first record)'}</span> },
              ]} className="sm:grid-cols-1" />
            )}
          </div>
        </div>
      )}
    </Drawer>
  );
}
