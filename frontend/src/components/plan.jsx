import React, { useEffect, useState } from 'react';
import { AlertTriangle, CheckCircle2, FileText, Info, Pencil, ShieldAlert, Sparkles } from 'lucide-react';
import { analytics } from '../lib/analytics';
import { buildPath, navigate } from '../lib/router';
import { formatDate, formatKw, formatLKR, formatPct, formatTemp, INTENT_LABELS } from '../lib/format';
import { Badge, Banner, Chip, StatTile } from './ui';
import { cn } from '../lib/utils';

export const AB_CONCISE = 'A_concise_summary';

/** The three numbers a manager decides on (spec §6.4 section A). */
export function PlanNumbers({ decision }) {
  const solver = decision?.solver_summary || {};
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
      <StatTile label="Savings" value={formatLKR(decision?.net_savings_lkr)} sub="Versus running without the battery plan" />
      <StatTile label="Savings (%)" value={formatPct(decision?.savings_percentage)} sub="Of tomorrow's energy and demand cost" />
      <StatTile
        label="Peak grid import"
        value={<span>{formatKw(solver.peak_demand_baseline_kw)} <span className="text-ink-3">→</span> {formatKw(solver.peak_demand_optimized_kw)}</span>}
        sub={decision?.peak_shaved_kw ? `${formatKw(decision.peak_shaved_kw, 1)} lower` : undefined}
      />
    </div>
  );
}

/**
 * Explanation shown per the XAI A/B test: variant A leads with the one-line numbers summary,
 * variant B with the full cited explanation. Either can expand to the other (fires explanation_opened).
 */
export function Explanation({ concise, full, variant, auditLogId }) {
  const conciseFirst = variant === AB_CONCISE && Boolean(concise);
  const [expanded, setExpanded] = useState(false);
  const toggle = () => {
    if (!expanded) analytics.explanationOpened(auditLogId);
    setExpanded((e) => !e);
  };
  const primary = conciseFirst ? concise : full;
  const secondary = conciseFirst ? full : concise;
  return (
    <div className="rounded-xl border border-line bg-surface p-4">
      <p className="mb-1 flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-ink-3">
        <Sparkles className="h-3.5 w-3.5" aria-hidden /> Why this plan
      </p>
      {/* Model-written text is rendered as plain text, never as Markdown or HTML (spec §9.5). */}
      <p className={cn('whitespace-pre-line text-ink', conciseFirst ? 'text-base font-medium' : 'text-sm leading-relaxed')}>{primary || 'No explanation was produced.'}</p>
      {secondary && (
        <>
          {expanded && <p className="mt-3 whitespace-pre-line border-t border-line pt-3 text-sm leading-relaxed text-ink-2">{secondary}</p>}
          <button type="button" onClick={toggle} aria-expanded={expanded} className="mt-2 text-sm font-medium text-accent-text hover:underline">
            {expanded ? 'Hide' : conciseFirst ? 'Show full explanation' : 'Show the one-line summary'}
          </button>
        </>
      )}
    </div>
  );
}

export function VerificationBadge({ audit }) {
  if (!audit) return null;
  if (audit.is_faithful === false) {
    return (
      <Badge tone="critical" icon={AlertTriangle} title={audit.reasoning}>
        Explanation failed the fact check — rely on the numbers
      </Badge>
    );
  }
  return (
    <Badge tone="good" icon={CheckCircle2} title={audit.reasoning}>
      Numbers checked against the solver
    </Badge>
  );
}

export function WarningsPanel({ warnings }) {
  if (!warnings?.length) return null;
  return (
    <Banner tone="warning" title={`${warnings.length} warning${warnings.length > 1 ? 's' : ''} to review`}>
      <ul className="list-disc space-y-1 pl-5">
        {warnings.map((w) => <li key={w}>{w}</li>)}
      </ul>
    </Banner>
  );
}

/** "We assumed…" chips (spec §6.2). "Change" pre-fills the question box. */
export function AssumptionChips({ assumptions, query }) {
  if (!assumptions?.length) return null;
  return (
    <div className="space-y-2">
      <p className="text-sm font-medium text-ink">We assumed…</p>
      <div className="flex flex-wrap gap-2">
        {assumptions.map((a) => (
          <span key={a} className="inline-flex items-center gap-2 rounded-full border border-warn/40 bg-warn-soft px-3 py-1 text-sm text-ink">
            <Info className="h-3.5 w-3.5 text-warn-text" aria-hidden />
            {a}
            {query && (
              <button type="button" onClick={() => navigate(buildPath('/ask', { q: query }))}
                className="inline-flex items-center gap-1 font-medium text-accent-text hover:underline">
                <Pencil className="h-3 w-3" aria-hidden /> Change
              </button>
            )}
          </span>
        ))}
      </div>
    </div>
  );
}

export function UnderstoodAs({ parsed }) {
  if (!parsed) return null;
  const items = [
    ['Request', INTENT_LABELS[parsed.action] || parsed.action],
    ['Room', parsed.room ? `${parsed.room}${parsed.room_explicit === false ? ' (assumed)' : ''}` : null],
    ['Date', parsed.date ? `${formatDate(parsed.date)}${parsed.date_explicit === false ? ' (assumed)' : ''}` : null],
    ['Target', parsed.action === 'optimize_dispatch' ? formatTemp(parsed.target_temp_c) : null],
    ['Outdoor change', parsed.perturb_temp_delta_c ? `+${parsed.perturb_temp_delta_c} °C` : null],
    ['Occupancy', parsed.perturb_occ_multiplier && parsed.perturb_occ_multiplier !== 1 ? `${parsed.perturb_occ_multiplier}×` : null],
  ].filter(([, v]) => v);
  return (
    <p className="text-sm text-ink-2">
      <span className="font-medium text-ink">Understood as: </span>
      {items.map(([k, v], i) => <span key={k}>{i > 0 && ' · '}{k}: <span className="text-ink">{v}</span></span>)}
      {parsed.intent_source === 'llm_router' && <span className="ml-1 text-ink-3">(interpreted by AI)</span>}
    </p>
  );
}

/** Neutral, never accusatory; never repeats the suspicious text (spec §6.2). */
export function SecurityNotice({ flags }) {
  if (!flags?.length) return null;
  return (
    <Banner tone="neutral" icon={ShieldAlert}>
      Part of your request looked like an instruction to the system and was treated as plain text. Limits were not changed.
    </Banner>
  );
}

export function ClauseCard({ citation, rank, onOpen, highlight }) {
  return (
    <article className="rounded-xl border border-line bg-surface p-4">
      <div className="mb-2 flex flex-wrap items-center gap-2 text-xs text-ink-2">
        {rank && <span className="rounded bg-surface-2 px-1.5 py-0.5 font-medium text-ink tabular">#{rank}</span>}
        <span className="font-medium text-ink">{citation.document_title}</span>
        {citation.effective_date && <span>· effective {formatDate(citation.effective_date)}</span>}
        {(citation.matched_by || []).map((m) => (
          <Badge key={m} tone="info">{m === 'semantic' ? 'Matched by meaning' : 'Matched by keywords'}</Badge>
        ))}
      </div>
      <h3 className="text-sm font-semibold text-ink">{citation.section_clause}</h3>
      <p className="mt-1 text-sm leading-relaxed text-ink-2">{highlight ? highlight(citation.content) : citation.content}</p>
      {onOpen && (
        <button type="button" onClick={onOpen} className="mt-2 inline-flex items-center gap-1 text-sm font-medium text-accent-text hover:underline">
          <FileText className="h-3.5 w-3.5" aria-hidden /> Open clause
        </button>
      )}
    </article>
  );
}

/** Fires recommendation_shown once per plan per session when a plan becomes visible. */
export function useRecommendationShown(auditLogId) {
  useEffect(() => { if (auditLogId) analytics.recommendationShown(auditLogId); }, [auditLogId]);
}

export function ScopeChips({ onPick }) {
  return (
    <div className="flex flex-wrap gap-2">
      {SUGGESTED_QUESTIONS.map((q) => <Chip key={q} onClick={() => onPick(q)}>{q}</Chip>)}
    </div>
  );
}

export const SUGGESTED_QUESTIONS = [
  'Plan tomorrow to avoid the evening peak',
  'What if it is 3 °C hotter tomorrow?',
  'What is the GP-2 peak rate?',
  "Show tomorrow's forecast",
];

/** Turns a what-if scenario into a planning question the parser reads the same way. */
export function scenarioToPlanQuestion(room, delta, occ) {
  const parts = [`Plan tomorrow's battery schedule for ${room}`];
  if (delta) parts.push(`on a day ${delta} °C hotter`);
  if (occ && occ !== 1) parts.push(occ > 1 ? `with ${Math.round((occ - 1) * 100)}% more students` : 'with half occupancy');
  return parts.join(' ');
}
