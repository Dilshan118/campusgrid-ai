import React, { useEffect, useRef, useState } from 'react';
import { CheckCircle2, Download, FileText, Hourglass, Info, Printer, RotateCcw, ThumbsDown, ThumbsUp, TriangleAlert } from 'lucide-react';
import { api } from '../api/client';
import { useAuth } from '../auth/AuthContext';
import { analytics } from '../lib/analytics';
import { announcePlansChanged, useAsync, useDraft, useNow } from '../lib/hooks';
import { buildPath, navigate } from '../lib/router';
import {
  expiresIn, formatDate, formatDateTime, formatKw, formatLKR, formatNumber, utcTitle,
} from '../lib/format';
import { BatteryLevelChart, BatteryPowerChart, GridImportChart } from '../components/charts';
import { CardSkeleton, useToast } from '../components/feedback';
import { ClauseCard, Explanation, PlanNumbers, VerificationBadge, WarningsPanel, useRecommendationShown } from '../components/plan';
import {
  Badge, Banner, Button, Card, Checkbox, ConfirmDialog, Dialog, EmptyState, ErrorPanel, Field,
  PageHeader, StatusPill, Textarea,
} from '../components/ui';

const TARIFF_ROWS = [
  { key: 'peak', label: 'Peak rate', window: 'peak', unit: '/kWh' },
  { key: 'day', label: 'Day rate', window: 'day', unit: '/kWh' },
  { key: 'off_peak', label: 'Off-peak rate', window: 'off_peak', unit: '/kWh' },
  { key: 'max_demand_penalty_lkr_kva', label: 'Maximum demand charge', unit: '/kVA per month' },
];

const PROVENANCE_TEXT = {
  reference_default: 'Not found in the retrieved documents — the reference PUCSL value was used.',
  rejected_out_of_range: 'The retrieved figure was implausible and was rejected — the reference PUCSL value was used.',
};

export default function PlanReviewPage({ params }) {
  const { data: record, error, loading, reload } = useAsync(() => api.auditRecord(params.id, { includeDetails: false }), [params.id]);

  if (loading && !record) {
    return (
      <div className="space-y-4" aria-busy="true">
        <div className="grid gap-3 sm:grid-cols-3"><CardSkeleton /><CardSkeleton /><CardSkeleton /></div>
        <CardSkeleton lines={5} />
      </div>
    );
  }
  if (error && !record) {
    return error.status === 404
      ? <EmptyState title={`Plan #${params.id} does not exist.`} action={<Button variant="secondary" onClick={() => navigate('/plans')}>Back to approvals</Button>} />
      : <ErrorPanel error={error} onRetry={reload} />;
  }
  if (record.record_type !== 'dispatch_recommendation') {
    return (
      <EmptyState title={`Record #${record.log_id} is not a dispatch plan.`}
        action={<Button variant="secondary" onClick={() => navigate(buildPath('/audit', { open: record.log_id }))}>Open in the audit trail</Button>}>
        Only dispatch plans go through approval.
      </EmptyState>
    );
  }
  return <PlanReview record={record} reload={reload} />;
}

function PlanReview({ record, reload }) {
  const { abVariant, can } = useAuth();
  const now = useNow(30_000);
  const [openCitation, setOpenCitation] = useState(null);
  useRecommendationShown(record.log_id);

  const decision = record.final_decision || {};
  const solver = decision.solver_summary || {};
  const target = decision.target || {};
  const citations = decision.citations || [];
  const status = record.effective_status;
  const expiry = expiresIn(record.timestamp, 24, now);

  const openClause = (citation) => {
    const rank = citations.indexOf(citation) + 1;
    analytics.citationClicked(record.log_id, rank || undefined, citation.section_clause);
    setOpenCitation({ citation, rank });
  };
  const goToDecision = (e) => {
    e?.preventDefault();
    document.getElementById('decision')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  // The summary bar appears once the headline numbers scroll out of view.
  const numbersRef = useRef(null);
  const [numbersVisible, setNumbersVisible] = useState(true);
  useEffect(() => {
    const node = numbersRef.current;
    if (!node || typeof IntersectionObserver === 'undefined') return undefined;
    const observer = new IntersectionObserver(([entry]) => setNumbersVisible(entry.isIntersecting), { threshold: 0 });
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  return (
    <div className="space-y-6 pb-16">
      <PageHeader
        breadcrumb={[{ label: 'Approvals', to: '/plans' }, { label: `Plan #${record.log_id}` }]}
        title={`Plan #${record.log_id}`}
        description={`${target.room || '—'} · ${formatDate(target.date)} · requested by ${record.user_id} · ${formatDateTime(record.timestamp)}`}
        actions={(
          <>
            <StatusPill status={status} />
            {status === 'pending' && <Badge tone={expiry.ms < 3 * 3600_000 ? 'warning' : 'neutral'} icon={Hourglass}>Expires in {expiry.label}</Badge>}
            <Button variant="secondary" size="sm" icon={Printer} onClick={() => window.print()} className="print:hidden">Print</Button>
            {status === 'pending' && can('audit:approve') && (
              <Button size="sm" onClick={goToDecision} className="print:hidden">Review &amp; decide</Button>
            )}
          </>
        )}
      />

      {/* A — the answer */}
      <section aria-labelledby="answer" className="space-y-4">
        <h2 id="answer" className="sr-only">The answer</h2>
        <div ref={numbersRef}><PlanNumbers decision={decision} /></div>
        <Explanation concise={decision.explanation_concise} full={decision.explanation} variant={abVariant} auditLogId={record.log_id} />
        <div className="flex flex-wrap items-center gap-2">
          <VerificationBadge audit={decision.faithfulness_audit} />
          <Badge tone="neutral">Solver: {solver.solver_status || '—'}{solver.solve_time_ms ? ` in ${formatNumber(solver.solve_time_ms)} ms` : ''}</Badge>
        </div>
      </section>

      {/* D — warnings, placed before the detail so they are read before deciding */}
      <WarningsPanel warnings={decision.warnings} />

      {/* B — schedule */}
      <Card title="The schedule" description="48 half-hour intervals. The shaded band is the 18:00–22:30 peak tariff window.">
        <div className="space-y-8">
          <GridImportChart slots={solver.time_slots} baseline={decision.baseline_grid_kw} optimized={solver.optimized_grid_kw} />
          <BatteryPowerChart slots={solver.time_slots} charge={solver.battery_charge_kw} discharge={solver.battery_discharge_kw} />
          <BatteryLevelChart slots={solver.time_slots} soc={solver.battery_soc_kwh} limits={decision.battery_limits} />
          <BindingLimits constraints={solver.binding_constraints} />
        </div>
      </Card>

      {/* C — inputs and sources */}
      <Card title="Why these numbers" description="What the plan was calculated from, and where each figure came from.">
        <div className="space-y-6">
          {decision.assumptions?.length > 0 && (
            <div>
              <h3 className="mb-1 text-sm font-semibold text-ink">What the system assumed</h3>
              <ul className="space-y-1 text-sm text-ink-2">
                {decision.assumptions.map((a) => (
                  <li key={a} className="flex items-start gap-1.5"><Info className="mt-0.5 h-4 w-4 shrink-0 text-warn-text" aria-hidden />{a}</li>
                ))}
              </ul>
            </div>
          )}
          <TariffInputs tariff={decision.tariff_inputs} citations={citations} onOpen={openClause} />
          <ComfortCheck feasibility={decision.thermal_feasibility} />
          {decision.forecast_summary && (
            <div>
              <h3 className="mb-1 text-sm font-semibold text-ink">Forecast summary</h3>
              <p className="text-sm text-ink-2">{decision.forecast_summary}</p>
            </div>
          )}
          <div>
            <h3 className="mb-2 text-sm font-semibold text-ink">Sources ({citations.length})</h3>
            <ol className="space-y-2">
              {citations.map((c, i) => (
                <li key={`${c.document_title}-${c.section_clause}`}>
                  <button type="button" onClick={() => openClause(c)}
                    className="flex w-full items-start gap-3 rounded-lg border border-line px-3 py-2 text-left text-sm hover:bg-surface-2">
                    <span className="rounded bg-surface-2 px-1.5 py-0.5 text-xs font-medium tabular">#{i + 1}</span>
                    <span className="min-w-0"><span className="font-medium text-ink">{c.section_clause}</span><span className="block text-xs text-ink-2">{c.document_title}</span></span>
                  </button>
                </li>
              ))}
            </ol>
          </div>
        </div>
      </Card>

      {/* E — decision */}
      <DecisionPanel record={record} decision={decision} status={status} expired={expiry.expired} canApprove={can('audit:approve')}
        canRerun={can('orchestrator:query')} onChanged={reload} />

      {!numbersVisible && (
        <div className="fixed inset-x-0 bottom-14 z-30 border-t border-line bg-surface/95 backdrop-blur lg:bottom-0 lg:left-64 print:hidden">
          <div className="mx-auto flex max-w-7xl items-center justify-between gap-3 px-4 py-2.5 lg:px-8">
            <p className="min-w-0 truncate text-sm text-ink-2">
              <span className="font-semibold text-ink">Plan #{record.log_id}</span>
              <span className="hidden sm:inline"> · {target.room} · {formatDate(target.date)}</span>
              {' · '}<span className="font-medium text-ink">{formatLKR(decision.net_savings_lkr)}</span> saving
              {decision.warnings?.length ? <span className="text-warn-text"> · {decision.warnings.length} warning{decision.warnings.length > 1 ? 's' : ''}</span> : null}
            </p>
            <div className="flex shrink-0 items-center gap-2">
              <StatusPill status={status} className="hidden sm:inline-flex" />
              {status === 'pending' && can('audit:approve') && <Button size="sm" onClick={goToDecision}>Review &amp; decide</Button>}
            </div>
          </div>
        </div>
      )}

      <Dialog open={Boolean(openCitation)} title={openCitation?.citation.section_clause} onClose={() => setOpenCitation(null)}>
        {openCitation && <ClauseCard citation={openCitation.citation} rank={openCitation.rank} />}
      </Dialog>
    </div>
  );
}

function BindingLimits({ constraints }) {
  if (!constraints?.length) return null;
  const grouped = constraints.reduce((acc, c) => {
    (acc[c.name] = acc[c.name] || []).push(c);
    return acc;
  }, {});
  return (
    <div>
      <h3 className="mb-1 text-sm font-semibold text-ink">Savings were limited by</h3>
      <ul className="list-disc space-y-1 pl-5 text-sm text-ink-2">
        {Object.entries(grouped).map(([name, items]) => {
          const slots = items.map((c) => c.time_slot).filter(Boolean);
          return (
            <li key={name}>
              <span className="text-ink">{name}</span> ({formatNumber(items[0].threshold, 0)}) at {slots.slice(0, 5).join(', ')}
              {slots.length > 5 && ` and ${slots.length - 5} more`}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function TariffInputs({ tariff, citations, onOpen }) {
  if (!tariff) return null;
  const rates = tariff.rates_lkr_kwh || {};
  const value = (key) => (key === 'max_demand_penalty_lkr_kva' ? tariff.max_demand_penalty_lkr_kva : rates[key]);
  const findCitation = (source) => citations.find((c) => source && source === `${c.document_title} — ${c.section_clause}`)
    || citations.find((c) => source && source.endsWith(c.section_clause));

  return (
    <div>
      <h3 className="mb-2 text-sm font-semibold text-ink">Tariff used</h3>
      <div className="overflow-x-auto rounded-lg border border-line">
        <table className="w-full text-sm">
          <thead className="bg-surface-2 text-left text-xs uppercase tracking-wide text-ink-2">
            <tr><th scope="col" className="px-3 py-2 font-medium">Figure</th><th scope="col" className="px-3 py-2 text-right font-medium">Value</th><th scope="col" className="px-3 py-2 font-medium">Window</th><th scope="col" className="px-3 py-2 font-medium">Source</th></tr>
          </thead>
          <tbody className="divide-y divide-line">
            {TARIFF_ROWS.map((row) => {
              const provenance = tariff.provenance?.[row.key];
              const source = tariff.source_clauses?.[row.key];
              const citation = findCitation(source);
              return (
                <tr key={row.key}>
                  <td className="px-3 py-2 text-ink">{row.label}</td>
                  <td className="px-3 py-2 text-right text-ink tabular">{formatLKR(value(row.key), { decimals: 2 })}<span className="text-ink-2">{row.unit}</span></td>
                  <td className="px-3 py-2 text-ink-2 tabular">{row.window ? tariff.windows?.[row.window] : 'Highest 15 minutes'}</td>
                  <td className="px-3 py-2">
                    {provenance === 'retrieved' ? (
                      citation ? (
                        <button type="button" onClick={() => onOpen(citation)} className="inline-flex items-center gap-1 rounded-md bg-accent-soft px-2 py-0.5 text-xs font-medium text-accent-text hover:underline">
                          <FileText className="h-3.5 w-3.5" aria-hidden />{citation.section_clause.split(' - ')[0]}
                        </button>
                      ) : <Badge tone="info">{(source || 'Retrieved').split(' — ').pop()}</Badge>
                    ) : (
                      <Badge tone="warning" icon={TriangleAlert} title={PROVENANCE_TEXT[provenance]}>Reference value</Badge>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ComfortCheck({ feasibility }) {
  if (!feasibility) return null;
  const [min, max] = feasibility.comfort_band_c || [21, 25.5];
  return (
    <div>
      <h3 className="mb-1 text-sm font-semibold text-ink">Comfort check</h3>
      {feasibility.is_feasible ? (
        <p className="flex items-center gap-1.5 text-sm text-ink-2"><CheckCircle2 className="h-4 w-4 text-good-text" aria-hidden />Indoor temperature stays within {min}–{max} °C.</p>
      ) : (
        <p className="flex items-center gap-1.5 text-sm text-ink-2"><TriangleAlert className="h-4 w-4 text-warn-text" aria-hidden />{feasibility.comfort_violations_count} half-hours fall outside {min}–{max} °C.</p>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Decision panel (spec §6.4 section E)
// ---------------------------------------------------------------------------

function DecisionPanel({ record, decision, status, expired, canApprove, canRerun, onChanged }) {
  const { notify } = useToast();
  const [notes, setNotes, clearNotes] = useDraft(`decision-${record.log_id}`);
  const [acknowledged, setAcknowledged] = useState(false);
  const [confirming, setConfirming] = useState(null); // 'approve' | 'reject'
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [justDecided, setJustDecided] = useState(null);
  const warnings = decision.warnings || [];

  async function submit() {
    const approved = confirming === 'approve';
    setBusy(true);
    setError(null);
    try {
      const result = await api.decide({
        log_id: record.log_id, approved, operator_notes: notes.trim() || null, acknowledge_warnings: approved && acknowledged,
      });
      setJustDecided(result);
      notify(`Plan #${record.log_id} ${approved ? 'approved' : 'rejected'}`, {
        detail: approved ? 'Recorded in the audit trail. Carry out the schedule through the BMS.' : 'The requester will see your reason on the plan.',
        tone: approved ? 'success' : 'info',
      });
      clearNotes();
      announcePlansChanged();
      onChanged();
    } catch (err) {
      setError(err);
      if (err.status === 409) onChanged(); // someone else decided, or it expired: show the current state
    } finally {
      setBusy(false);
      setConfirming(null);
    }
  }

  const decided = record.decision;

  return (
    <Card title="Decision" id="decision" className="scroll-mt-20 print:hidden">
      <div className="space-y-4">
        {error && <ErrorPanel error={error} />}

        {(justDecided || decided) && (
          <DecidedView record={record} decided={decided || justDecided} decision={decision} fresh={Boolean(justDecided)} />
        )}

        {!decided && !justDecided && (status === 'expired' || expired) && (
          <Banner tone="neutral" icon={Hourglass} title="This plan has expired"
            action={canRerun && <Button variant="secondary" icon={RotateCcw} onClick={() => navigate(buildPath('/ask', { q: record.query_text }))}>Re-run with today's data</Button>}>
            Plans are valid for 24 hours because the forecast and weather change.
          </Banner>
        )}

        {!decided && !justDecided && status === 'pending' && !expired && (canApprove ? (
          <>
            <Field label="Notes" htmlFor="decision-notes" hint="Required when rejecting. Recorded permanently with your decision.">
              <Textarea id="decision-notes" value={notes} maxLength={2000} onChange={(e) => setNotes(e.target.value)}
                placeholder="For example: Approved — exam timetable confirmed." />
            </Field>
            {warnings.length > 0 && (
              <Checkbox id="ack-warnings" checked={acknowledged} onChange={setAcknowledged}>
                I have reviewed the {warnings.length} warning{warnings.length > 1 ? 's' : ''} above.
              </Checkbox>
            )}
            <div className="flex flex-wrap gap-2">
              <Button icon={ThumbsUp} disabled={warnings.length > 0 && !acknowledged} onClick={() => setConfirming('approve')}>Approve</Button>
              <Button variant="secondary" icon={ThumbsDown} disabled={!notes.trim()} onClick={() => setConfirming('reject')}
                title={!notes.trim() ? 'Add a reason in Notes to reject' : undefined}>Reject</Button>
            </div>
            <p className="text-xs text-ink-2">CampusGrid does not operate equipment. Approving records your decision; the team carries out the schedule.</p>
          </>
        ) : (
          <p className="text-sm text-ink-2">Waiting for a facility manager to review.</p>
        ))}
      </div>

      <ConfirmDialog
        open={Boolean(confirming)}
        busy={busy}
        title={confirming === 'approve' ? `Approve plan #${record.log_id}?` : `Reject plan #${record.log_id}?`}
        confirmLabel={confirming === 'approve' ? 'Approve plan' : 'Reject plan'}
        confirmVariant={confirming === 'approve' ? 'primary' : 'danger'}
        onConfirm={submit}
        onCancel={() => setConfirming(null)}
      >
        <p>It will be recorded permanently in the audit trail and cannot be undone.</p>
        {confirming === 'approve' && <p className="mt-2">Savings {formatLKR(decision.net_savings_lkr)} · peak {formatKw(decision.solver_summary?.peak_demand_optimized_kw)}.</p>}
      </ConfirmDialog>
    </Card>
  );
}

function DecidedView({ record, decided, decision, fresh }) {
  const approved = (decided.status || decided.decision) === 'approved';
  return (
    <div className="space-y-3">
      <Banner tone={approved ? 'success' : 'neutral'}
        title={`${approved ? 'Approved' : 'Rejected'} by ${decided.decided_by} · ${formatDateTime(decided.decided_at)}`}>
        {decided.notes && <p>“{decided.notes}”</p>}
        {fresh && approved && <p className="mt-1">Recorded. CampusGrid does not operate equipment — carry out the schedule through the building management system.</p>}
      </Banner>
      {approved && (
        <Button variant="secondary" icon={Download} onClick={() => downloadChecklist(record, decided, decision)}>Download execution checklist</Button>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Execution checklist: the approved schedule as a plain-text list of actions
// ---------------------------------------------------------------------------

function scheduleActions(solver) {
  const slots = solver.time_slots || [];
  const actions = slots.map((slot, i) => {
    const charge = solver.battery_charge_kw?.[i] || 0;
    const discharge = solver.battery_discharge_kw?.[i] || 0;
    if (charge > 0.5) return { slot, kind: 'Charge', kw: Math.round(charge) };
    if (discharge > 0.5) return { slot, kind: 'Discharge', kw: Math.round(discharge) };
    return { slot, kind: null, kw: 0 };
  });
  const end = (slot) => {
    const [h, m] = slot.split(':').map(Number);
    const t = h * 60 + m + 30;
    return `${String(Math.floor(t / 60) % 24).padStart(2, '0')}:${String(t % 60).padStart(2, '0')}`;
  };
  const merged = [];
  actions.forEach((a) => {
    const last = merged[merged.length - 1];
    if (a.kind && last && last.kind === a.kind && last.kw === a.kw && last.to === a.slot) last.to = end(a.slot);
    else if (a.kind) merged.push({ kind: a.kind, kw: a.kw, from: a.slot, to: end(a.slot) });
  });
  return merged;
}

function downloadChecklist(record, decided, decision) {
  const solver = decision.solver_summary || {};
  const target = decision.target || {};
  const lines = [
    `CampusGrid AI — execution checklist for plan #${record.log_id}`,
    `Room ${target.room || '—'} · ${target.date || '—'} · target ${target.target_temp_c ?? '—'} °C`,
    `Approved by ${decided.decided_by} at ${formatDateTime(decided.decided_at)} (${utcTitle(decided.decided_at)})`,
    decided.notes ? `Notes: ${decided.notes}` : null,
    `Expected savings ${formatLKR(decision.net_savings_lkr)} · peak ${formatKw(solver.peak_demand_baseline_kw)} → ${formatKw(solver.peak_demand_optimized_kw)}`,
    '',
    'CampusGrid does not operate equipment. Carry out each step through the building management system and tick it off.',
    '',
    'Battery schedule (Asia/Colombo time):',
    ...scheduleActions(solver).map((a) => `[ ] ${a.from}–${a.to}  ${a.kind} at ${a.kw} kW`),
    '',
    ...(decision.warnings?.length ? ['Warnings acknowledged at approval:', ...decision.warnings.map((w) => `- ${w}`), ''] : []),
    'Carried out by: ____________________   Date/time: ____________________',
  ].filter((l) => l !== null);

  const blob = new Blob([lines.join('\n')], { type: 'text/plain;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `campusgrid-plan-${record.log_id}-checklist.txt`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

