import React, { useEffect, useRef, useState } from 'react';
import { ArrowRight, BookOpen, CheckCircle2, ChevronDown, Circle, History, Loader2, RotateCcw, Send, SlidersHorizontal } from 'lucide-react';
import { api } from '../api/client';
import { useAuth } from '../auth/AuthContext';
import { useDraft, announcePlansChanged } from '../lib/hooks';
import { sessionStore } from '../lib/storage';
import { buildPath, navigate } from '../lib/router';
import { formatKw, formatLKR, formatNumber, INTENT_LABELS, relativeTime } from '../lib/format';
import { ForecastChart, TemperatureChart } from '../components/charts';
import {
  AssumptionChips, ClauseCard, Explanation, PlanNumbers, ScopeChips, SecurityNotice, UnderstoodAs,
  VerificationBadge, WarningsPanel, scenarioToPlanQuestion, useRecommendationShown,
} from '../components/plan';
import { Banner, Button, Card, ErrorPanel, PageHeader, Slider, StatusPill, Textarea } from '../components/ui';
import { useElapsed } from '../components/feedback';
import { cn } from '../lib/utils';

const MAX_QUERY = 2000;
const HISTORY_KEY = 'cg-ask-history';

const STEPS = [
  { key: 'understand', label: 'Understanding' },
  { key: 'forecast', label: 'Forecast' },
  { key: 'comfort', label: 'Comfort check' },
  { key: 'regulations', label: 'Regulations' },
  { key: 'plan', label: 'Plan & explanation' },
];
const STEPS_RUN = {
  ready_for_operator_approval: ['understand', 'forecast', 'comfort', 'regulations', 'plan'],
  simulation_completed: ['understand', 'forecast', 'comfort'],
  policy_info_retrieved: ['understand', 'regulations'],
  forecast_ready: ['understand', 'forecast'],
  out_of_scope: ['understand'],
};

const slots48 = (n) => Array.from({ length: n }, (_, i) => `${String(Math.floor(i / 2)).padStart(2, '0')}:${i % 2 ? '30' : '00'}`);

export default function AskPage({ query }) {
  const { abVariant } = useAuth();
  const [question, setQuestion] = useDraft('ask');
  const [showOverrides, setShowOverrides] = useState(false);
  const [overrides, setOverrides] = useState({ temp: 0, occ: 1, touchedTemp: false, touchedOcc: false });
  const [running, setRunning] = useState(false);
  const [activeStep, setActiveStep] = useState(0);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [history, setHistory] = useState(() => sessionStore.get(HISTORY_KEY, []));
  const inputRef = useRef(null);

  // Pre-fill from links such as "Plan for this scenario" or an assumption chip's "Change".
  useEffect(() => {
    if (query.q) { setQuestion(query.q); inputRef.current?.focus(); }
  }, [query.q, setQuestion]);

  // "/" focuses the question box from anywhere on the page (unless you are already typing).
  useEffect(() => {
    const onKey = (e) => {
      if (e.key !== '/' || e.metaKey || e.ctrlKey || e.altKey) return;
      const tag = document.activeElement?.tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || document.activeElement?.isContentEditable) return;
      e.preventDefault();
      inputRef.current?.focus();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  // Progress animation while the request runs (the server does not stream steps).
  useEffect(() => {
    if (!running) return undefined;
    setActiveStep(0);
    const t = setInterval(() => setActiveStep((s) => Math.min(s + 1, STEPS.length - 1)), 1100);
    return () => clearInterval(t);
  }, [running]);

  async function ask(text = question) {
    const q = text.trim();
    if (q.length < 2 || running) return;
    setRunning(true);
    setError(null);
    setResult(null);
    const payload = { query: q };
    if (overrides.touchedTemp) payload.perturb_temp_delta_c = overrides.temp;
    if (overrides.touchedOcc) payload.perturb_occ_multiplier = overrides.occ;
    try {
      const data = await api.ask(payload);
      setResult(data);
      if (data.requires_human_approval) announcePlansChanged();
      const entry = { id: data.audit_log_id, query: q, status: data.status, at: new Date().toISOString(), result: data };
      const next = [entry, ...history.filter((h) => h.id !== entry.id)].slice(0, 8);
      setHistory(next);
      sessionStore.set(HISTORY_KEY, next);
    } catch (err) {
      setError(err);
    } finally {
      setRunning(false);
    }
  }

  const pick = (q) => { setQuestion(q); inputRef.current?.focus(); };

  return (
    <div>
      <PageHeader title="Ask CampusGrid" description="Ask in plain English. CampusGrid forecasts, checks comfort, looks up the tariff rules and proposes a plan — a facility manager approves it before anything happens." />

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_300px]">
        <div className="min-w-0 space-y-6">
          <Card>
            <form onSubmit={(e) => { e.preventDefault(); ask(); }} className="space-y-3">
              <label htmlFor="question" className="sr-only">Your question</label>
              <Textarea id="question" ref={inputRef} value={question} maxLength={MAX_QUERY} disabled={running}
                onChange={(e) => setQuestion(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) ask(); }}
                placeholder="For example: Tomorrow looks hot — precool Lecture Hall 1 to 23.5 °C and cut the peak demand charge" />
              {!question && <ScopeChips onPick={pick} />}

              <div className="rounded-lg border border-line">
                <button type="button" onClick={() => setShowOverrides((s) => !s)} aria-expanded={showOverrides}
                  className="flex w-full items-center justify-between px-4 py-2.5 text-sm font-medium text-ink hover:bg-surface-2">
                  <span className="inline-flex items-center gap-2"><SlidersHorizontal className="h-4 w-4 text-ink-2" aria-hidden />
                    Override the question {(overrides.touchedTemp || overrides.touchedOcc) && <span className="text-accent-text">(active)</span>}</span>
                  <ChevronDown className={cn('h-4 w-4 text-ink-2 transition-transform', showOverrides && 'rotate-180')} aria-hidden />
                </button>
                {showOverrides && (
                  <div className="grid gap-4 border-t border-line p-4 sm:grid-cols-2">
                    <Slider id="ov-temp" label="Outdoor temperature change" min={-10} max={15} step={0.5} value={overrides.temp}
                      format={(v) => `${v > 0 ? '+' : ''}${v} °C`} onChange={(v) => setOverrides((o) => ({ ...o, temp: v, touchedTemp: true }))}
                      hint={overrides.touchedTemp ? 'Sent with the question' : 'Not sent — the question text is used'} />
                    <Slider id="ov-occ" label="Occupancy multiplier" min={0} max={5} step={0.1} value={overrides.occ}
                      format={(v) => `${v.toFixed(1)}×`} onChange={(v) => setOverrides((o) => ({ ...o, occ: v, touchedOcc: true }))}
                      hint={overrides.touchedOcc ? 'Sent with the question' : 'Not sent — the question text is used'} />
                    <div className="sm:col-span-2">
                      <Button variant="ghost" size="sm" icon={RotateCcw} onClick={() => setOverrides({ temp: 0, occ: 1, touchedTemp: false, touchedOcc: false })}>Reset overrides</Button>
                    </div>
                  </div>
                )}
              </div>

              <div className="flex flex-wrap items-center justify-between gap-3">
                <p className="text-xs text-ink-2"><kbd className="rounded border border-line-strong px-1">/</kbd> to focus · <kbd className="rounded border border-line-strong px-1">Ctrl/⌘ + Enter</kbd> to ask</p>
                <Button type="submit" icon={Send} loading={running} disabled={question.trim().length < 2}>Ask</Button>
              </div>
            </form>
          </Card>

          {running && <ProgressSteps active={activeStep} />}
          {error && !running && <ErrorPanel error={error} onRetry={() => ask()} />}
          {result && !running && <ResultView result={result} abVariant={abVariant} onAsk={pick} />}
        </div>

        <HistoryPanel history={history} onOpen={(h) => { setResult(h.result); setError(null); setQuestion(h.query); }} />
      </div>
    </div>
  );
}

function ProgressSteps({ active }) {
  const elapsed = useElapsed(true);
  return (
    <Card title="Working on it" actions={<span className="text-sm text-ink-2 tabular" aria-live="off">{elapsed} s</span>}>
      <ol className="flex flex-wrap gap-x-6 gap-y-3" aria-live="polite">
        {STEPS.map((step, i) => (
          <li key={step.key} className="flex items-center gap-2 text-sm">
            {i < active ? <CheckCircle2 className="h-4 w-4 text-good-text" aria-hidden />
              : i === active ? <Loader2 className="h-4 w-4 animate-spin text-accent-text" aria-hidden />
                : <Circle className="h-4 w-4 text-ink-3" aria-hidden />}
            <span className={i <= active ? 'text-ink' : 'text-ink-3'}>{step.label}</span>
          </li>
        ))}
      </ol>
      <p className="mt-3 text-xs text-ink-2">Only the steps your question needs will run. A full plan can take several seconds.</p>
    </Card>
  );
}

function StepsRan({ status }) {
  const ran = STEPS_RUN[status] || [];
  return (
    <p className="text-xs text-ink-2">
      Ran: {STEPS.filter((s) => ran.includes(s.key)).map((s) => s.label).join(' → ')}
    </p>
  );
}

function ResultView({ result, abVariant, onAsk }) {
  const body = {
    ready_for_operator_approval: <PlanResult result={result} abVariant={abVariant} />,
    simulation_completed: <SimulationResult result={result} />,
    policy_info_retrieved: <PolicyResult result={result} />,
    forecast_ready: <ForecastResult result={result} onAsk={onAsk} />,
    out_of_scope: <OutOfScopeResult result={result} onAsk={onAsk} />,
  }[result.status] || <Banner tone="neutral">{result.explanation}</Banner>;

  return (
    <div className="space-y-4" aria-live="polite">
      {body}
      <div className="space-y-3 rounded-xl border border-line bg-surface p-4">
        <UnderstoodAs parsed={result.parsed_intent} />
        <AssumptionChips assumptions={result.assumptions} query={result.parsed_intent?.raw_query} />
        <SecurityNotice flags={result.security_flags} />
        <StepsRan status={result.status} />
      </div>
    </div>
  );
}

function PlanResult({ result, abVariant }) {
  useRecommendationShown(result.audit_log_id);
  const rec = result.recommendation || {};
  return (
    <Card
      title={`Dispatch plan #${result.audit_log_id}`}
      description="Awaiting facility manager approval. Nothing has been switched."
      actions={<StatusPill status="pending" />}
    >
      <div className="space-y-4">
        <PlanNumbers decision={rec} />
        <Explanation concise={result.explanation_concise} full={result.explanation} variant={abVariant} auditLogId={result.audit_log_id} />
        <div className="flex flex-wrap items-center gap-2"><VerificationBadge audit={rec.faithfulness_audit} /></div>
        <WarningsPanel warnings={result.warnings} />
        <Button icon={ArrowRight} onClick={() => navigate(`/plans/${result.audit_log_id}`)}>Open plan review</Button>
      </div>
    </Card>
  );
}

function SimulationResult({ result }) {
  const twin = result.digital_twin_feasibility || {};
  const indoor = twin.simulated_indoor_temps_c || [];
  const band = [twin.comfort_limits?.min_c ?? 21, twin.comfort_limits?.max_c ?? 25.5];
  const violations = twin.comfort_violations_count || 0;
  const applied = twin.perturbation_applied || {};
  const parsed = result.parsed_intent || {};
  return (
    <Card title="What-if simulation" description={`Outdoor change ${applied.temp_delta_c > 0 ? '+' : ''}${applied.temp_delta_c ?? 0} °C · occupancy ${applied.occupancy_multiplier ?? 1}×`}>
      <div className="space-y-4">
        <Banner tone={violations ? 'warning' : 'success'} title={violations ? `${violations} half-hours outside the comfort band` : 'Comfort maintained all day'} />
        <TemperatureChart slots={slots48(indoor.length)} indoor={indoor} outdoor={twin.ambient_temperatures_c} band={band} />
        <Button variant="secondary" icon={ArrowRight}
          onClick={() => navigate(buildPath('/ask', { q: scenarioToPlanQuestion(parsed.room || 'LH-1', applied.temp_delta_c, applied.occupancy_multiplier) }))}>
          Plan for this scenario
        </Button>
      </div>
    </Card>
  );
}

function PolicyResult({ result }) {
  const rules = result.extracted_rules || {};
  const rates = rules.rates_lkr_kwh || {};
  const citations = (result.citations || []).slice(0, 3);
  return (
    <Card title="Regulations" description={result.explanation}>
      <div className="space-y-4">
        {citations.map((c, i) => <ClauseCard key={`${c.document_title}-${c.section_clause}`} citation={c} rank={i + 1} />)}
        {rates.peak !== undefined && (
          <div className="rounded-lg bg-surface-2 p-3 text-sm text-ink-2">
            Figures read from these clauses: peak {formatLKR(rates.peak, { decimals: 2 })}/kWh · day {formatLKR(rates.day, { decimals: 2 })}/kWh ·
            off-peak {formatLKR(rates.off_peak, { decimals: 2 })}/kWh · demand charge {formatLKR(rules.max_demand_penalty_lkr_kva, { decimals: 2 })}/kVA
          </div>
        )}
        <Button variant="secondary" icon={BookOpen} onClick={() => navigate(buildPath('/regulations', { q: result.parsed_intent?.raw_query }))}>Open in Regulations</Button>
      </div>
    </Card>
  );
}

function ForecastResult({ result, onAsk }) {
  const f = result.forecast || {};
  const rec = result.recommendation || {};
  return (
    <Card title="Forecast" description={rec.target_date ? `For ${rec.target_date}` : undefined}>
      <div className="space-y-4">
        <p className="text-sm text-ink">{result.explanation}</p>
        <p className="text-sm text-ink-2">Peak {formatKw(rec.peak_demand_kw)} at {rec.peak_time_slot} · {formatNumber(rec.anomaly_count)} flagged intervals</p>
        <ForecastChart slots={f.time_slots} demand={f.forecast_demand_kw} solar={f.forecast_solar_kw} lower={f.lower_bound_kw} upper={f.upper_bound_kw} />
        <Button variant="secondary" icon={ArrowRight} onClick={() => onAsk("Plan tomorrow's battery schedule to cut the evening peak")}>Plan tomorrow</Button>
      </div>
    </Card>
  );
}

function OutOfScopeResult({ result, onAsk }) {
  return (
    <Card title="Outside what CampusGrid can help with">
      <p className="mb-4 text-sm text-ink-2">{result.explanation}</p>
      <ScopeChips onPick={onAsk} />
    </Card>
  );
}

function HistoryPanel({ history, onOpen }) {
  return (
    <aside aria-label="This session's questions" className="min-w-0">
      <Card title="This session" bodyClassName="p-0">
        {history.length === 0 ? (
          <p className="flex items-center gap-2 px-5 py-4 text-sm text-ink-2"><History className="h-4 w-4" aria-hidden /> Your questions will appear here.</p>
        ) : (
          <ul className="divide-y divide-line">
            {history.map((h) => (
              <li key={h.id}>
                <button type="button" onClick={() => onOpen(h)} className="w-full px-5 py-3 text-left hover:bg-surface-2">
                  <p className="line-clamp-2 text-sm text-ink">{h.query}</p>
                  <p className="mt-0.5 text-xs text-ink-2">{INTENT_LABELS[h.result?.parsed_intent?.action] || h.status} · #{h.id} · {relativeTime(h.at)}</p>
                </button>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </aside>
  );
}
